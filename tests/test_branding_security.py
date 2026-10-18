"""Namespace colors must stay data across API, storage and dashboard rendering."""
from contextlib import nullcontext
import json
from types import SimpleNamespace

import pytest
from flask import Flask
from pydantic import ValidationError

from vault.schemas import BRAND_COLOR_FIELDS, NamespaceCreate


PAYLOADS = [
    '#112233"><img src=x onerror=alert(1)>',
    '#112233;}</style><script>window.parent.__branding_probe=1</script><style>',
    '#112233\n', '#123', 'red', 123, False, [], {},
]


def _color_update(field, value):
    return {"color": value} if field == "color" else {"metadata": {field: value}}


@pytest.mark.parametrize("field", BRAND_COLOR_FIELDS)
@pytest.mark.parametrize("value", PAYLOADS)
def test_creation_schema_rejects_unsafe_colors(field, value):
    with pytest.raises(ValidationError):
        NamespaceCreate(slug="branding", display_name="Brand", **_color_update(field, value))


@pytest.fixture
def branding_env(monkeypatch):
    # The shared DB fixture uses SECRET_KEY; Settings requires this variable.
    monkeypatch.setenv("CLAUDEOS_SECRET_KEY", "branding-test-secret-32-characters!!")


@pytest.fixture
def namespace_client(branding_env, fresh_db, monkeypatch, tmp_path):
    from core.auth import create_access_token, create_user
    from core.api.routes.projects import projects_bp
    from vault import manager

    monkeypatch.setattr(manager, "VAULT_ROOT", tmp_path / "vault")
    manager.create_namespace(NamespaceCreate(slug="branding", display_name="Brand",
                                             metadata={"company_name": "Example"}))
    user = create_user("brand_operator", "BrandOperator123!", role="operator")
    token = create_access_token(user["id"], user["username"], "operator", None)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(projects_bp)
    with app.test_client() as client:
        yield client, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize("field", BRAND_COLOR_FIELDS)
@pytest.mark.parametrize("value", PAYLOADS[:3])
def test_api_rejects_unsafe_colors_before_storage(namespace_client, method, field, value):
    from vault.manager import get_namespace_by_slug

    client, headers = namespace_client
    body = _color_update(field, value)
    path = "/api/v1/namespaces/branding"
    if method == "POST":
        path = "/api/v1/namespaces"
        body.update(slug="rejected", display_name="Rejected")
    response = client.open(path, method=method, headers=headers, json=body)
    assert response.status_code == 422, response.json
    assert get_namespace_by_slug("rejected") is None
    ns = get_namespace_by_slug("branding")
    assert ns.color == "#407E3C"
    assert ns.metadata == {"company_name": "Example"}


@pytest.mark.parametrize("metadata", [None, [], "#112233", 123])
def test_patch_rejects_non_object_metadata(namespace_client, metadata):
    client, headers = namespace_client
    response = client.patch("/api/v1/namespaces/branding", headers=headers,
                            json={"metadata": metadata})
    assert response.status_code == 422


def test_api_preserves_valid_palette_and_unrelated_metadata(namespace_client):
    client, headers = namespace_client
    metadata = {field: "#aAbBcC" for field in BRAND_COLOR_FIELDS if field != "color"}
    metadata.update(company_name="Example", custom_setting={"enabled": True})
    created = client.post("/api/v1/namespaces", headers=headers, json={
        "slug": "valid-brand", "display_name": "Valid", "color": "#123456", "metadata": metadata,
    })
    assert created.status_code == 201, created.json
    assert created.json["metadata"] == metadata
    # Optional colors still support clearing overrides and falling back to the theme.
    metadata.update(accent_color="", text_muted_color=None)
    updated = client.patch("/api/v1/namespaces/valid-brand", headers=headers,
                           json={"color": "#abcdef", "metadata": metadata})
    assert updated.status_code == 200, updated.json
    assert updated.json["color"] == "#abcdef"
    assert updated.json["metadata"] == metadata


def test_legacy_metadata_is_safe_to_load_without_rewriting_storage(namespace_client):
    from core.database import get_db

    client, headers = namespace_client
    metadata = {field: PAYLOADS[1] for field in BRAND_COLOR_FIELDS if field != "color"}
    metadata.update(company_name="Example", custom_setting=True)
    raw = json.dumps(metadata)
    with get_db() as conn:
        conn.execute("UPDATE namespaces SET metadata=? WHERE slug='branding'", (raw,))
    for path in ("/api/v1/namespaces/branding", "/api/v1/namespaces"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        data = response.json if isinstance(response.json, dict) else response.json[0]
        assert data["metadata"] == {"company_name": "Example", "custom_setting": True}
    with get_db() as conn:
        assert conn.execute("SELECT metadata FROM namespaces WHERE slug='branding'").fetchone()[0] == raw


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("field", BRAND_COLOR_FIELDS)
def test_cached_colors_cannot_escape_dashboard_html_or_iframe(monkeypatch, theme, field):
    from dashboard.components import brand
    from dashboard._pages import _overview

    cached = {"color": "#407E3C", "company_name": "Example", field: PAYLOADS[1]}
    monkeypatch.setattr(brand.st, "session_state", {"ns_brand": cached, "theme": theme})
    html = []
    monkeypatch.setattr(brand.st, "markdown", lambda value, **kw: html.append(value))
    monkeypatch.setattr(brand.st, "sidebar", SimpleNamespace(markdown=lambda value, **kw: html.append(value)))
    monkeypatch.setattr(brand.st, "columns", lambda count: [nullcontext() for _ in range(count)])
    monkeypatch.setattr(brand._components, "html", lambda value, **kw: html.append(value))
    brand.sidebar_logo()
    brand.empty_state("◈", "Title", "Body")
    brand.aurora_hero("Title", pill="Pill")
    _overview._render_live_refresh_toggle()
    _overview._render_kpi_grid([("Custom", 1, "")])
    html.append(brand._ns_brand_css(cached, _theme_override=theme))
    assert field not in brand.get_ns_brand()
    assert all("__branding_probe" not in value for value in html)
    assert cached[field] == PAYLOADS[1]  # Filtering must not mutate session data.


def test_valid_cached_palette_reaches_dashboard_unchanged(monkeypatch):
    from dashboard.components import brand

    palette = {field: "#aAbBcC" for field in BRAND_COLOR_FIELDS}
    palette.update(company_name="Example", icon="🏢")
    monkeypatch.setattr(brand.st, "session_state", {"ns_brand": palette})
    assert brand.get_ns_brand() == palette
