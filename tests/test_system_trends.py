"""/system/trends — per-day series feeding the Overview KPI sparklines."""
import pytest


def _login(client, name, pw):
    r = client.post("/api/v1/auth/login", json={"username": name, "password": pw})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.json['access_token']}"}


def test_trends_requires_auth(client):
    assert client.get("/api/v1/system/trends").status_code == 401


def test_trends_shape_and_length(client, auth_headers):
    r = client.get("/api/v1/system/trends?days=7", headers=auth_headers)
    assert r.status_code == 200
    body = r.json
    assert len(body["days"]) == 7
    assert body["days"] == sorted(body["days"])
    for name in ("memory", "runs", "outputs", "open_tickets", "workflows"):
        assert len(body["series"][name]) == 7
        assert all(isinstance(n, int) and n >= 0 for n in body["series"][name])


def test_trends_days_is_clamped_and_validated(client, auth_headers):
    assert len(client.get("/api/v1/system/trends?days=1000", headers=auth_headers).json["days"]) == 90
    assert len(client.get("/api/v1/system/trends?days=0", headers=auth_headers).json["days"]) == 2
    assert client.get("/api/v1/system/trends?days=abc", headers=auth_headers).status_code == 400


def test_trends_counts_new_records_and_scopes_clients(client, auth_headers):
    from core.auth import create_user
    from vault.manager import create_namespace
    from vault.schemas import NamespaceCreate
    from outputs.manager import save
    for slug in ("ns-a", "ns-b"):
        create_namespace(NamespaceCreate(slug=slug, display_name=slug, type="client"))
    create_user("client_a", "ClientA1234!", role="client", namespace="ns-a")
    save(namespace="ns-a", title="mine", content="a")
    save(namespace="ns-b", title="theirs-1", content="b")
    save(namespace="ns-b", title="theirs-2", content="b")

    admin = client.get("/api/v1/system/trends?days=3", headers=auth_headers).json
    assert admin["series"]["outputs"][-1] == 3          # admin sees every namespace

    mine = client.get("/api/v1/system/trends?days=3",
                      headers=_login(client, "client_a", "ClientA1234!")).json
    assert mine["namespace"] == "ns-a"
    assert mine["series"]["outputs"][-1] == 1           # client sees only own namespace


# ── Dashboard sparkline renderer ────────────────────────────────────────────

def test_sparkline_renders_polyline_for_real_data():
    from dashboard._pages._overview import _sparkline_svg
    svg = _sparkline_svg([0, 2, 1, 5, 3], "#407E3C")
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg.count("<polyline") == 1 and "#407E3C" in svg


@pytest.mark.parametrize("values", [[], [4], [0, 0, 0, 0]])
def test_sparkline_is_empty_when_nothing_to_draw(values):
    from dashboard._pages._overview import _sparkline_svg
    assert _sparkline_svg(values, "#407E3C") == ""


def test_sparkline_points_stay_inside_viewbox():
    import re
    from dashboard._pages._overview import _sparkline_svg
    svg = _sparkline_svg([0, 9, 3, 9, 1], "#000", width=84, height=28)
    line = re.search(r'<polyline points="([^"]+)"', svg).group(1)
    for pair in line.split():
        x, y = map(float, pair.split(","))
        assert 0 <= x <= 84 and 0 <= y <= 28
