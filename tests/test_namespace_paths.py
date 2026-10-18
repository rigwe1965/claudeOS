"""Namespace provisioning must not escape the namespace's vault directory."""
from unittest.mock import Mock

import pytest
from flask import Flask

from vault import manager
from vault.schemas import NamespaceCreate


INVALID_SLUGS = [
    "", ".", "..", "../escaped", "tenant/../../escaped", "tenant/nested",
    r"..\escaped", r"C:\escaped", "C:escaped", r"\\server\share",
    "tenant\n", "tenant\x00", "Tenant", "tenant_name",
]


@pytest.fixture
def namespace_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "namespace-test-secret-32-characters!!")
    monkeypatch.setattr(manager, "VAULT_ROOT", tmp_path / "vault")


@pytest.fixture
def namespace_client(namespace_env, fresh_db):
    from core.auth import create_access_token, create_user
    from core.api.routes.projects import projects_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(projects_bp)

    def headers(role):
        user = create_user(role, "NamespaceUser123!", role=role)
        token = create_access_token(user["id"], user["username"], role, None)
        return {"Authorization": f"Bearer {token}"}

    with app.test_client() as client:
        yield client, headers


@pytest.mark.parametrize("slug", INVALID_SLUGS)
def test_manager_rejects_invalid_slug_before_database_access(namespace_env, monkeypatch, slug):
    database = Mock(side_effect=AssertionError("Invalid slug reached database"))
    monkeypatch.setattr(manager, "get_db", database)

    with pytest.raises(ValueError, match="Invalid namespace slug"):
        manager.create_namespace(NamespaceCreate(slug=slug, display_name="Rejected"))

    database.assert_not_called()
    assert not manager.VAULT_ROOT.exists()


@pytest.mark.parametrize("role", ["admin", "operator"])
@pytest.mark.parametrize("slug", ["../escaped", "tenant/../../escaped", r"..\escaped", "tenant\n", "absolute"])
def test_api_rejects_unsafe_slug_without_side_effects(namespace_client, tmp_path, role, slug):
    client, headers = namespace_client
    if slug == "absolute":
        slug = str(tmp_path / "escaped")

    response = client.post("/api/v1/namespaces", headers=headers(role),
                           json={"slug": slug, "display_name": "Rejected"})

    assert response.status_code == 400, response.json
    assert manager.get_namespace_by_slug(slug) is None
    assert not manager.VAULT_ROOT.exists()
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("slug", ["../escaped", r"..\escaped", "tenant\n"])
def test_provisioner_validates_direct_calls(namespace_env, slug):
    with pytest.raises(ValueError, match="Invalid namespace slug"):
        manager._provision_workspace(slug)
    assert not manager.VAULT_ROOT.exists()


@pytest.mark.parametrize("link_location", ["namespace", "context", "outputs"])
def test_symlink_escape_rejected_before_any_directory_creation(namespace_client, tmp_path, link_location):
    client, headers = namespace_client
    root = manager.VAULT_ROOT
    root.mkdir()
    outside = tmp_path / "vault-outside"
    outside.mkdir()
    link = root / "tenant"
    if link_location != "namespace":
        link.mkdir()
        link /= link_location
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are unavailable in this environment")
    before = set(root.rglob("*"))

    response = client.post("/api/v1/namespaces", headers=headers("operator"),
                           json={"slug": "tenant", "display_name": "Rejected"})

    assert response.status_code == 400, response.json
    assert manager.get_namespace_by_slug("tenant") is None
    assert set(root.rglob("*")) == before
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("role", ["admin", "operator"])
@pytest.mark.parametrize("slug", ["a", "tenant-42"])
def test_valid_namespace_provisions_and_supports_context(namespace_client, role, slug):
    client, make_headers = namespace_client
    headers = make_headers(role)

    response = client.post("/api/v1/namespaces", headers=headers,
                           json={"slug": slug, "display_name": "Tenant"})

    assert response.status_code == 201, response.json
    assert manager.get_namespace_by_slug(slug).id == response.json["id"]
    workspace = manager.VAULT_ROOT / slug
    assert {path.name for path in workspace.iterdir()} == set(manager.WORKSPACE_SUBDIRS)
    written = client.post(f"/api/v1/namespaces/{slug}/context", headers=headers,
                          json={"filename": "brief.md", "content": "Tenant context"})
    assert written.status_code == 201, written.json
    assert manager.read_context(slug, "brief.md") == "Tenant context"


def test_unauthenticated_request_cannot_provision(namespace_client):
    client, _ = namespace_client
    response = client.post("/api/v1/namespaces", json={"slug": "tenant", "display_name": "Tenant"})
    assert response.status_code == 401
    assert manager.get_namespace_by_slug("tenant") is None
    assert not manager.VAULT_ROOT.exists()
