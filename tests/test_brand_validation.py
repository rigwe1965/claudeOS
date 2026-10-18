"""Namespace branding colours must be strict hex on create and update (XSS via style/attribute injection)."""
import pytest

XSS = '#fff;" onmouseover="alert(1)'
COLOR_KEYS = ("accent_color", "bg_color", "hover_color", "surface_color", "surface2_color",
              "text_color", "text_muted_color", "border_color", "input_bg")


@pytest.mark.parametrize("key", COLOR_KEYS)
def test_create_rejects_non_hex_metadata_color(client, admin_token, key):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/api/v1/namespaces", headers=h, json={
        "slug": "brand-bad", "display_name": "Brand Bad", "metadata": {key: XSS}})
    assert r.status_code == 422, r.json


@pytest.mark.parametrize("key", COLOR_KEYS)
def test_update_rejects_non_hex_metadata_color(client, admin_token, key):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/api/v1/namespaces", headers=h, json={
        "slug": "brand-ok", "display_name": "Brand OK", "metadata": {"accent_color": "#407E3C"}})
    assert r.status_code == 201, r.json
    r = client.patch("/api/v1/namespaces/brand-ok", headers=h, json={"metadata": {key: XSS}})
    assert r.status_code == 422, r.json
    r = client.patch("/api/v1/namespaces/brand-ok", headers=h, json={"metadata": {key: "#407E3C"}})
    assert r.status_code == 200, r.json
