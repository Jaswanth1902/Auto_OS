"""
voice/transcribe.py — Speech-to-text via Google Gemini Flash.

Uses the new google-genai SDK (v1.65+) for multimodal audio transcription.
Falls back to local faster-whisper if Gemini is unavailable.
"""
import os
import subprocess
import tempfile
import uuid
from utils.logger import api_logger as logger

def _preprocess_audio(file_path: str) -> str:
    """
    Resamples the audio to 16kHz, 16-bit mono WAV format for Whisper,
    and checks if the duration exceeds 30 seconds to prevent resource exhaustion.
    Returns the path to the new pre-processed audio file.
    """
    try:
        # Check duration
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())

        if duration > 30.0:
            logger.warning(f"Audio file exceeds 30 seconds ({duration}s). Truncating to 30s.")
            duration_str = "30"
        else:
            duration_str = str(duration)

        # Convert to 16kHz mono WAV
        out_path = os.path.join(tempfile.gettempdir(), f"_voice_proc_{uuid.uuid4().hex}.wav")
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", file_path,
            "-t", duration_str,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            out_path
        ]
        subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
        return out_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to preprocess audio: {e.stderr}")
        raise RuntimeError("Audio preprocessing failed.")
    except Exception as e:
        logger.error(f"Unexpected error during audio preprocessing: {e}")
        raise RuntimeError("Audio preprocessing failed.")


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file using Gemini Flash.
    Falls back to local faster-whisper if Gemini is unavailable.
    """
    # Pre-process the audio before transcription to fix sample rate mismatches and duration crashes
    processed_path = _preprocess_audio(file_path)

    try:
        api_key = os.getenv("GOOGLE_API_KEY", "")

        if api_key:
            try:
                return _transcribe_gemini(processed_path, api_key)
            except Exception as e:
                logger.warning("Gemini transcription failed, falling back to local: %s", e)

        return _transcribe_local(processed_path)
    finally:
        # Cleanup the processed file
        if os.path.exists(processed_path):
            os.remove(processed_path)


def _transcribe_gemini(file_path: str, api_key: str) -> str:
    """Transcribe using Gemini Flash via the new google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Read audio file
    with open(file_path, "rb") as f:
        audio_data = f.read()

    # Preprocessed audio is always wav
    mime = "audio/wav"

    # Build the audio part
    audio_part = types.Part.from_bytes(data=audio_data, mime_type=mime)

    prompt = (
        "Transcribe the following audio exactly as spoken. "
        "Return ONLY the transcribed text, nothing else. "
        "No preamble, no quotes, no explanation. Just the raw words spoken."
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=[prompt, audio_part],
    )

    text = response.text.strip().strip('"').strip("'")
    logger.info("Gemini transcription: '%s'", text)
    return text


def _transcribe_local(file_path: str) -> str:
    """Fallback: transcribe using local faster-whisper."""
    from faster_whisper import WhisperModel

    model_size = os.getenv("WHISPER_MODEL", "base")
    logger.info("Using local faster-whisper model: %s", model_size)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(
        file_path,
        beam_size=5,
        language="en",
        vad_filter=True,
    )

    text = " ".join(seg.text.strip() for seg in segments).strip()
    logger.info("Local transcription (%s, %.1fs): '%s'", info.language, info.duration, text)
    return text
