"""Voice note parser: Meta media_id → downloaded .ogg → Whisper transcript.

The transcript is then fed into the same pipeline as a text message. Audio bytes
and the transcript itself are never logged (Critical Rule #1).
"""
from __future__ import annotations

from typing import Optional

from app.ai.whisper import transcribe
from app.utils.logger import get_logger
from app.whatsapp.client import download_media, get_media_url

logger = get_logger("voice")


async def parse(media_id: str, media_url: Optional[str] = None) -> str:
    url = media_url or await get_media_url(media_id)
    audio = await download_media(url)
    transcript = await transcribe(audio, filename="voice.ogg", language="hi")
    logger.info("voice_transcribed", extra={"media_id": media_id, "chars": len(transcript)})
    return transcript
