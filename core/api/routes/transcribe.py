"""Transcribe route — POST /api/v1/transcribe
Accepts a WAV audio blob, runs Whisper (numpy path, no ffmpeg), returns {"text": "..."}.
"""
import io
from flask import Blueprint, request, jsonify
from core.auth import require_auth

transcribe_bp = Blueprint("transcribe", __name__, url_prefix="/api/v1")

# Common WAV rates keep reduced resampling factors <= 1764 at 16 kHz,
# bounding SciPy's filter allocation as well as the output below.
_SUPPORTED_SAMPLE_RATES = frozenset({
    8000, 11025, 12000, 16000, 22050, 24000, 32000,
    44100, 48000, 88200, 96000, 176400, 192000,
})
_MAX_AUDIO_SECONDS = 300


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

        if sample_rate not in _SUPPORTED_SAMPLE_RATES:
            return jsonify({"error": "Unsupported audio sample rate"}), 400
        target_sr = whisper.audio.SAMPLE_RATE
        output_samples = (data.shape[0] * target_sr + sample_rate - 1) // sample_rate
        if output_samples > target_sr * _MAX_AUDIO_SECONDS:
            return jsonify({"error": "Audio exceeds five minute limit"}), 413

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
