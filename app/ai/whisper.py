"""OpenAI Whisper transcription wrapper.

Transcribes Hindi/Hinglish voice notes. Retries come free from the shared
AsyncOpenAI client (max_retries=3). NEVER log the returned transcript
(Critical Rule #1) — callers log ids/length only.
"""
from __future__ import annotations

from app.ai.openai_client import get_openai
from app.utils.logger import get_logger

logger = get_logger("whisper")


async def transcribe(audio: bytes, filename: str = "audio.ogg", language: str = "hi") -> str:
    client = get_openai()
    resp = await client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio),
        language=language,
    )
    return resp.text
