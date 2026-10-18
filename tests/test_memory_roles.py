"""Staff (tickets-only) must have no access to any memory route."""
import pytest

ROUTES = [
    ("get", "/api/v1/memory"),
    ("post", "/api/v1/memory"),
    ("delete", "/api/v1/memory/bulk"),
    ("get", "/api/v1/memory/some-id"),
    ("put", "/api/v1/memory/some-id"),
    ("delete", "/api/v1/memory/some-id"),
    ("post", "/api/v1/memory/search"),
    ("get", "/api/v1/memory/namespaces"),
    ("get", "/api/v1/memory/context/any"),
    ("get", "/api/v1/memory/hybrid-search"),
]


@pytest.mark.parametrize("method,path", ROUTES)
def test_staff_denied_on_memory_routes(client, admin_token, method, path):
    from core.auth import create_user
    create_user("staff_m", "StaffMem1234!", role="staff", namespace=None)
    r = client.post("/api/v1/auth/login", json={"username": "staff_m", "password": "StaffMem1234!"})
    h = {"Authorization": f"Bearer {r.json['access_token']}"}
    assert getattr(client, method)(path, headers=h, json={}).status_code == 403


def test_operator_still_allowed(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    assert client.get("/api/v1/memory", headers=h).status_code == 200
