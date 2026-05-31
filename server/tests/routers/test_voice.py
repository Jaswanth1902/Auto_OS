import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

@patch("voice.transcribe.transcribe_audio")
def test_voice_transcribe(mock_transcribe):
    mock_transcribe.return_value = "Hello world"

    # Create fake audio content
    fake_audio = b"fake audio data that is reasonably long to pass the minimum 500 byte limit in the endpoint" * 10
    files = {"audio": ("test.webm", fake_audio, "audio/webm")}

    response = client.post("/voice/transcribe", files=files)
    assert response.status_code == 200
    assert response.json()["text"] == "Hello world"
    assert response.json()["success"] is True
