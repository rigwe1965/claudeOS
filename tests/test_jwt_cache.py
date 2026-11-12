"""JWT cache expiration regressions using signed tokens and controlled clocks."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest

from core import auth


@pytest.fixture
def token_clock(monkeypatch):
    clock = SimpleNamespace(wall=2_000_000_000.0, monotonic=100.0)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(clock.wall, tz=tz)

    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDatetime)
    monkeypatch.setattr(auth, "time", SimpleNamespace(
        time=lambda: clock.wall, monotonic=lambda: clock.monotonic,
    ))
    monkeypatch.setattr(auth, "_jwt_cache", {})
    monkeypatch.setattr(auth, "_secret", lambda: "jwt-cache-regression-test-secret-32-chars")
    return clock


@pytest.mark.parametrize("remaining", [2, 120, None])
def test_valid_cache_hit_and_deadline(token_clock, monkeypatch, remaining):
    payload = {"sub": "test-user"}
    if remaining is not None:
        payload["exp"] = str(int(token_clock.wall + remaining))
    token = jwt.encode(payload, auth._secret(), algorithm="HS256")
    decode = Mock(wraps=auth.decode_access_token)
    monkeypatch.setattr(auth, "decode_access_token", decode)

    assert auth._cached_decode_access_token(token) == payload
    deadline = auth._jwt_cache[auth.hashlib.sha256(token.encode()).hexdigest()][1]
    assert deadline == token_clock.monotonic + min(remaining or 60, 60)
    token_clock.wall += 1
    token_clock.monotonic += 1
    assert auth._cached_decode_access_token(token) == payload
    assert decode.call_count == 1


@pytest.mark.parametrize("monotonic_delta", [2, 0.1])
def test_cached_expired_token_blocks_protected_reads_and_writes(
        client, token_clock, monotonic_delta):
    from core.database import get_db

    user = auth.create_user("cache_admin", "CacheAdmin123!", role="admin", namespace=None)
    payload = auth.decode_access_token_unverified(auth.create_access_token(
        user["id"], user["username"], user["role"], user["namespace"],
    ))
    payload["exp"] = int(token_clock.wall + 2)
    token = jwt.encode(payload, auth._secret(), algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/outputs", headers=headers).status_code == 200

    # Also simulate a wall-clock jump while the monotonic cache TTL is still live.
    token_clock.wall += 2
    token_clock.monotonic += monotonic_delta
    read = client.get("/api/v1/outputs", headers=headers)
    write = client.post("/api/v1/outputs", headers=headers, json={
        "namespace": "global", "title": "expired", "content": "must not be saved",
    })
    assert read.status_code == write.status_code == 401
    assert read.json == write.json == {"error": "Token expired"}
    assert auth.hashlib.sha256(token.encode()).hexdigest() not in auth._jwt_cache
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 0


def test_expiration_uses_pyjwt_integer_semantics(token_clock):
    payload = {"sub": "test-user", "exp": token_clock.wall + 2.9}
    token = jwt.encode(payload, auth._secret(), algorithm="HS256")
    assert auth._cached_decode_access_token(token) == payload
    token_clock.wall += 2
    token_clock.monotonic += 0.1
    with pytest.raises(jwt.ExpiredSignatureError):
        auth._cached_decode_access_token(token)


def test_cache_ttl_still_requires_reverification(token_clock, monkeypatch):
    payload = {"sub": "test-user", "exp": int(token_clock.wall + 120)}
    token = jwt.encode(payload, auth._secret(), algorithm="HS256")
    decode = Mock(wraps=auth.decode_access_token)
    monkeypatch.setattr(auth, "decode_access_token", decode)
    assert auth._cached_decode_access_token(token) == payload
    token_clock.wall += 60
    token_clock.monotonic += 60
    assert auth._cached_decode_access_token(token) == payload
    assert decode.call_count == 2
