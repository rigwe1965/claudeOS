"""Header-declared WAV sample rate / duration must be bounded before resampling."""
import io
import sys
import types
import wave

import numpy as np
import pytest


def _wav(rate, n_samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.zeros(n_samples, dtype=np.int16).tobytes())
    return buf.getvalue()


@pytest.fixture()
def fake_whisper(monkeypatch):
    mod = types.ModuleType("whisper")
    mod.audio = types.SimpleNamespace(SAMPLE_RATE=16000)
    monkeypatch.setitem(sys.modules, "whisper", mod)


@pytest.mark.parametrize("rate,n", [(1, 100_000), (7_999, 1_000), (400_000, 1_000), (8_000, 8_000 * 601)])
def test_oversized_projection_is_rejected(client, admin_token, fake_whisper, rate, n):
    pytest.importorskip("scipy")
    r = client.post("/api/v1/transcribe", headers={"Authorization": f"Bearer {admin_token}"},
                    data={"audio": (io.BytesIO(_wav(rate, n)), "a.wav")}, content_type="multipart/form-data")
    assert r.status_code == 400, r.json
