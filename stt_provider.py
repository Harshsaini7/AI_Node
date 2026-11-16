"""
STT Provider
============
Local speech-to-text using faster-whisper (runs on CPU, no cloud, no API key).

The browser records the microphone and sends the audio to the server. This module
turns those audio bytes into text:

    from stt_provider import transcribe
    text = transcribe(audio_bytes)   # "" when there is no speech

The model is loaded once, on first use. Choose it with WHISPER_MODEL in .env
(default "base.en"). The model files are downloaded once from Hugging Face and
cached under ~/.cache/huggingface.

Audio is decoded from memory. It is never written to disk.

Phase 4.1 - Speech-to-Text
"""

import io
import os
import threading

from logger import log

# English-only models are smaller and more accurate for English than the multilingual ones.
DEFAULT_WHISPER_MODEL = "base.en"

_model = None
_model_lock = threading.Lock()  # one load at a time, one transcription at a time


class SttError(Exception):
    """Raised when audio cannot be transcribed (bad audio or model failure)."""


def _get_model():
    """Load the Whisper model once (lazy). Caller must hold _model_lock."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # imported late: heavy import

        name = os.getenv("WHISPER_MODEL", DEFAULT_WHISPER_MODEL).strip() or DEFAULT_WHISPER_MODEL
        log.info(f"Loading speech model '{name}' (first use may download it)...")
        _model = WhisperModel(name, device="cpu", compute_type="int8")
        log.info("Speech model ready.")
    return _model


def transcribe(audio_bytes):
    """
    Convert recorded audio to text.

    Args:
        audio_bytes (bytes): Audio file content (webm/opus, ogg, wav, mp4 ...)

    Returns:
        str: The recognised text, or "" if the audio is empty or has no speech

    Raises:
        SttError: If the audio cannot be decoded or the model fails
    """
    if not audio_bytes:
        return ""

    try:
        with _model_lock:
            model = _get_model()
            segments, _info = model.transcribe(
                io.BytesIO(audio_bytes),
                language="en",
                beam_size=1,
                vad_filter=True,  # drop silence so it is not turned into made-up text
                condition_on_previous_text=False,
                temperature=0.0,
            )
            # 'segments' is lazy: decoding errors surface while iterating
            parts = [segment.text.strip() for segment in segments if segment.no_speech_prob < 0.6]
    except Exception as error:
        log.error(f"Speech-to-text failed: {error}", exc_info=True)
        raise SttError("Speech-to-text failed") from error

    return " ".join(part for part in parts if part).strip()


if __name__ == "__main__":
    # Standalone check: python stt_provider.py path\to\audio.wav
    import sys

    if len(sys.argv) != 2:
        print("Usage: python stt_provider.py <audio file>")
        raise SystemExit(1)
    with open(sys.argv[1], "rb") as audio_file:
        print(repr(transcribe(audio_file.read())))
