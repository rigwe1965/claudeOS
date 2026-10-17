"""Transcribe route — POST /api/v1/transcribe
Accepts a WAV audio blob, runs Whisper (numpy path, no ffmpeg), returns {"text": "..."}.
"""
import io
from flask import Blueprint, request, jsonify
from core.auth import require_auth

transcribe_bp = Blueprint("transcribe", __name__, url_prefix="/api/v1")


@transcribe_bp.route("/transcribe", methods=["POST"])
@require_auth
def transcribe_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400

    audio_bytes = request.files["audio"].read()
    if not audio_bytes:
        return jsonify({"error": "Empty audio"}), 400

    try:
        import numpy as np
        import whisper
        from scipy.io import wavfile

        sample_rate, data = wavfile.read(io.BytesIO(audio_bytes))

        # Convert to float32 mono
        if data.ndim > 1:
            data = data.mean(axis=1)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        else:
            data = data.astype(np.float32)

        # Resample to 16 kHz if needed
        target_sr = whisper.audio.SAMPLE_RATE
        if sample_rate != target_sr:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(sample_rate, target_sr)
            data = resample_poly(data, target_sr // g, sample_rate // g).astype(np.float32)

        model = _get_model()
        result = model.transcribe(data, fp16=False, language="en", temperature=0)
        text = result.get("text", "").strip()
        return jsonify({"text": text})

    except ImportError:
        return jsonify({"error": "openai-whisper not installed"}), 501
    except Exception:
        import logging
        logging.getLogger("claudeos.transcribe").exception("transcription failed")
        return jsonify({"error": "Transcription failed"}), 500


_whisper_model = None

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model("base")
    return _whisper_model
