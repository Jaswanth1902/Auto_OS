"""
routers/voice.py — HTTP endpoint for voice transcription.
"""
import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from utils.logger import api_logger as logger

router = APIRouter(prefix="/voice", tags=["voice"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


class TranscriptionResponse(BaseModel):
    text: str
    success: bool


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_endpoint(audio: UploadFile = File(...)):
    """
    Receives an audio file (e.g., .webm from the browser MediaRecorder),
    transcribes it via Gemini Flash, and returns the text.
    """
    # Save uploaded file to a temp path
    ext = ".webm"
    if audio.content_type:
        if "wav" in audio.content_type:
            ext = ".wav"
        elif "ogg" in audio.content_type:
            ext = ".ogg"
        elif "mp3" in audio.content_type:
            ext = ".mp3"

    tmp_path = os.path.join(DATA_DIR, f"_voice_{uuid.uuid4().hex}{ext}")

    try:
        content = await audio.read()
        if len(content) < 500:
            raise HTTPException(status_code=400, detail="Audio too short. Please hold longer.")

        with open(tmp_path, "wb") as f:
            f.write(content)

        logger.info("Received audio: %d bytes, type=%s", len(content), audio.content_type)

        from voice.transcribe import transcribe_audio
        text = transcribe_audio(tmp_path)

        if not text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio. Please try again.")

        return TranscriptionResponse(text=text, success=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Transcription error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
