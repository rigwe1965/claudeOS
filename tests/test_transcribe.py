"""Bound WAV resampling before SciPy or Whisper can allocate oversized inputs."""
import io
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import numpy as np
import pytest
from flask import Flask
from scipy.io import wavfile
from scipy import signal

from core import auth
from core.api.routes import transcribe


@pytest.fixture
def audio_client(monkeypatch):
    secret = "transcribe-test-secret-32-characters!"
    monkeypatch.setattr(auth, "_secret", lambda: secret)
    monkeypatch.setattr(auth, "_user_state", lambda _: {
        "is_active": True, "tokens_valid_after": 0, "must_change_password": False,
        "role": "operator", "namespace": None,
    })
    token = jwt.encode({"sub": "audio-user", "username": "audio-user"}, secret,
                       algorithm="HS256")
    monkeypatch.setattr(auth, "_jwt_cache", {})
    monkeypatch.setitem(sys.modules, "whisper", SimpleNamespace(
        audio=SimpleNamespace(SAMPLE_RATE=16000),
    ))
    model = Mock()
    model.transcribe.return_value = {"text": "  speech  "}
    get_model = Mock(return_value=model)
    monkeypatch.setattr(transcribe, "_get_model", get_model)
    app = Flask(__name__)
    app.config.update(TESTING=True, MAX_CONTENT_LENGTH=20 * 1024 * 1024)
    app.register_blueprint(transcribe.transcribe_bp)
    with app.test_client() as client:
        yield client, {"Authorization": f"Bearer {token}"}, get_model


def post_wav(audio_client, rate, frames, channels=1):
    client, headers, _ = audio_client
    buf = io.BytesIO()
    shape = (frames,) if channels == 1 else (frames, channels)
    wavfile.write(buf, rate, np.zeros(shape, dtype=np.int16))
    buf.seek(0)
    return client.post("/api/v1/transcribe", headers=headers,
                       data={"audio": (buf, "voice.wav")})


@pytest.mark.parametrize("rate", [0, 1, 7999, 47999, 191999, 192001, 1_000_000_007])
def test_unsafe_rates_rejected_before_resampling_or_model(audio_client, monkeypatch, rate):
    resample = Mock(side_effect=AssertionError("Unsafe rate reached SciPy"))
    monkeypatch.setattr(signal, "resample_poly", resample)
    # At 1 Hz, this sub-MiB file would expand to 3.2 billion output samples.
    response = post_wav(audio_client, rate, 200_000 if rate == 1 else 1)
    assert response.status_code == 400
    assert response.json == {"error": "Unsupported audio sample rate"}
    resample.assert_not_called()
    audio_client[2].assert_not_called()


@pytest.mark.parametrize("rate", [8000, 16000])
def test_over_duration_rejected_including_native_rate(audio_client, monkeypatch, rate):
    resample = Mock(side_effect=AssertionError("Oversized audio reached SciPy"))
    monkeypatch.setattr(signal, "resample_poly", resample)
    response = post_wav(audio_client, rate, rate * 300 + 1)
    assert response.status_code == 413
    assert response.json == {"error": "Audio exceeds five minute limit"}
    resample.assert_not_called()
    audio_client[2].assert_not_called()


@pytest.mark.parametrize("rate", [
    8000, 11025, 12000, 16000, 22050, 24000, 32000,
    44100, 48000, 88200, 96000, 176400, 192000,
])
@pytest.mark.parametrize("channels", [1, 2])
def test_supported_wav_reaches_model_as_float32_mono(audio_client, rate, channels):
    frames = rate // 100
    response = post_wav(audio_client, rate, frames, channels)
    assert response.status_code == 200
    assert response.json == {"text": "speech"}
    model = audio_client[2].return_value
    model.transcribe.assert_called_once()
    args, kwargs = model.transcribe.call_args
    audio = args[0]
    assert audio.dtype == np.float32
    assert audio.shape == ((frames * 16000 + rate - 1) // rate,)
    assert kwargs == {"fp16": False, "language": "en", "temperature": 0}


@pytest.mark.parametrize("rate", [8000, 16000])
def test_exact_duration_limit_is_accepted(audio_client, rate):
    response = post_wav(audio_client, rate, rate * 300)
    assert response.status_code == 200
    audio = audio_client[2].return_value.transcribe.call_args.args[0]
    assert audio.shape == (16000 * 300,)


def test_authentication_and_missing_audio_errors(audio_client):
    client, headers, get_model = audio_client
    assert client.post("/api/v1/transcribe").status_code == 401
    assert client.post("/api/v1/transcribe", headers=headers).status_code == 400
    response = client.post("/api/v1/transcribe", headers=headers,
                           data={"audio": (io.BytesIO(), "empty.wav")})
    assert response.status_code == 400
    assert response.json == {"error": "Empty audio"}
    get_model.assert_not_called()
