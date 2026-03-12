# bot/transcriber.py
"""Whisper-based audio transcription."""
import openai
from bot.config import OPENAI_API_KEY

_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


async def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """Transcribe audio bytes using OpenAI Whisper API."""
    import io
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice.ogg"
    response = await _client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return response.text
