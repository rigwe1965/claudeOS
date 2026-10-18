"""Output role policy, namespace isolation, and storage access regressions."""
import pytest


@pytest.fixture
def output_access(app, monkeypatch, tmp_path):
    from core.auth import create_access_token, create_user
    from outputs import manager
    from vault import manager as vault
    from vault.schemas import NamespaceCreate

    monkeypatch.setattr(manager, "STORE_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(vault, "VAULT_ROOT", tmp_path / "vault")
    outputs = []
    for slug in ("ns-a", "ns-b"):
        vault.create_namespace(NamespaceCreate(slug=slug, display_name=slug, type="client"))
        outputs.append(manager.save(namespace=slug, title="secret", content=f"private {slug}"))

    def headers(role, namespace=None):
        user = create_user("output_user", "OutputUser123!", role=role, namespace=namespace)
        token = create_access_token(user["id"], user["username"], role, namespace)
        return {"Authorization": f"Bearer {token}"}

    return outputs, headers


def _requests(output_id):
    return [
        ("GET", "", None),
        ("GET", "?namespace=ns-b", None),
        ("GET", "/search?q=secret", None),
        ("GET", "/stats", None),
        ("GET", "/stats/all", None),
        ("GET", f"/{output_id}", None),
        ("GET", f"/{output_id}/content", None),
        ("GET", f"/{output_id}/export", None),
        ("GET", f"/{output_id}/export?format=markdown", None),
        ("POST", "", {"namespace": "ns-b", "title": "injected", "content": "bad"}),
        ("DELETE", f"/{output_id}", None),
        ("DELETE", "/bulk", {"ids": [output_id]}),
    ]


@pytest.mark.parametrize("role, namespace", [("staff", None), ("staff", "ns-a"), ("unknown", None)])
def test_roles_without_output_access_never_reach_storage(client, output_access, monkeypatch, role, namespace):
    from outputs import manager

    outputs, make_headers = output_access
    headers = make_headers(role, namespace)

    def forbidden_storage(*args, **kwargs):
        pytest.fail("Unauthorized output request reached storage")

    for name in ("list_outputs", "search", "get_stats", "get_stats_all", "get_by_id", "save", "delete", "delete_bulk"):
        monkeypatch.setattr(manager, name, forbidden_storage)
    for method, path, body in _requests(outputs[0].id):
        response = client.open(f"/api/v1/outputs{path}", method=method, headers=headers, json=body)
        assert response.status_code == 403, (method, path, response.get_data(as_text=True))


@pytest.mark.parametrize("role", ["admin", "operator", "client", "viewer"])
def test_output_read_permissions(client, output_access, role):
    outputs, make_headers = output_access
    scoped = role in ("client", "viewer")
    headers = make_headers(role, "ns-a" if scoped else None)
    expected_ids = {outputs[0].id} if scoped else {out.id for out in outputs}

    listing = client.get("/api/v1/outputs", headers=headers)
    assert listing.status_code == 200
    assert {row["id"] for row in listing.json} == expected_ids
    search = client.get("/api/v1/outputs/search?q=secret", headers=headers)
    assert search.status_code == 200
    assert {row["id"] for row in search.json} == expected_ids
    stats = client.get("/api/v1/outputs/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json["total_count"] == len(expected_ids)
    all_stats = client.get("/api/v1/outputs/stats/all", headers=headers)
    assert all_stats.status_code == (403 if scoped else 200)

    filtered = client.get("/api/v1/outputs?namespace=ns-b", headers=headers)
    assert filtered.status_code == 200
    assert {row["id"] for row in filtered.json} == ({outputs[0].id} if scoped else {outputs[1].id})
    for out in outputs:
        allowed = out.id in expected_ids
        for suffix in ("", "/content", "/export", "/export?format=text"):
            response = client.get(f"/api/v1/outputs/{out.id}{suffix}", headers=headers)
            assert response.status_code == (200 if allowed else 404)
            if allowed:
                assert out.content in response.get_data(as_text=True)


@pytest.mark.parametrize("role", ["admin", "operator", "client", "viewer"])
def test_output_write_permissions(client, output_access, role):
    from outputs.manager import list_outputs

    outputs, make_headers = output_access
    headers = make_headers(role, "ns-a" if role in ("client", "viewer") else None)
    created = client.post("/api/v1/outputs", headers=headers,
                          json={"namespace": "ns-b", "title": "new", "content": "new content"})
    if role == "viewer":
        assert created.status_code == 403
        for method, path, body in _requests(outputs[0].id):
            if method == "DELETE":
                assert client.open(f"/api/v1/outputs{path}", method=method, headers=headers, json=body).status_code == 403
        assert {out.id for out in list_outputs()} == {out.id for out in outputs}
        return

    assert created.status_code == 201
    assert created.json["namespace"] == ("ns-a" if role == "client" else "ns-b")
    assert client.delete(f"/api/v1/outputs/{created.json['id']}", headers=headers).status_code == 200
    if role == "client":
        assert client.delete(f"/api/v1/outputs/{outputs[1].id}", headers=headers).status_code == 404
    deleted = client.delete("/api/v1/outputs/bulk", headers=headers, json={"ids": [out.id for out in outputs]})
    assert deleted.status_code == 200
    assert set(deleted.json["deleted"]) == ({outputs[0].id} if role == "client" else {out.id for out in outputs})
    assert deleted.json["failed"] == ([outputs[1].id] if role == "client" else [])


@pytest.mark.parametrize("namespace", ["global", "ns-a"])
@pytest.mark.parametrize("permissions", [["read"], ["read", "write"]])
def test_output_api_key_permissions(client, output_access, namespace, permissions):
    from core.api.auth import create_api_key

    outputs, _ = output_access
    raw_key, _ = create_api_key("output-key", permissions=permissions, namespace=namespace)
    headers = {"X-API-Key": raw_key}
    listing = client.get("/api/v1/outputs", headers=headers)
    assert listing.status_code == 200
    assert {row["id"] for row in listing.json} == ({outputs[0].id} if namespace == "ns-a" else {out.id for out in outputs})
    created = client.post("/api/v1/outputs", headers=headers,
                          json={"namespace": "ns-b", "title": "new", "content": "new content"})
    assert created.status_code == (201 if "write" in permissions else 403)
    if "write" in permissions:
        assert created.json["namespace"] == ("ns-a" if namespace == "ns-a" else "ns-b")
