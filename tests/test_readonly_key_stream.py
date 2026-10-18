"""A read-only API key must not start agent runs through the GET stream endpoint."""


def test_read_only_api_key_cannot_stream_agent(client, admin_token):
    adm = {"Authorization": f"Bearer {admin_token}"}
    k = client.post("/api/v1/admin/api-keys", headers=adm, json={"name": "ro-stream", "permissions": ["read"]})
    key = {"X-API-Key": k.json["raw_key"]}
    r = client.get("/api/v1/agents/any-agent/stream?prompt=hi&save_output=true", headers=key)
    assert r.status_code == 403
    from core.database import get_db
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0] == 0
