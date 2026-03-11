# bot/handlers.py
import io
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot import transcriber, brain
from bot.vault import git_sync
from bot.config import VAULT_REPO_PATH

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Full pipeline: voice → transcribe → agent → reply."""
    msg = update.message
    await msg.reply_text("🎙️ Transcribing...")

    voice_file = await context.bot.get_file(msg.voice.file_id)
    audio_buffer = io.BytesIO()
    await voice_file.download_to_memory(audio_buffer)

    try:
        transcript = await transcriber.transcribe_audio_bytes(audio_buffer.getvalue())
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        await msg.reply_text("❌ Transcription failed. Please try again.")
        return

    await msg.reply_text(f"📝 *Transcript:* {transcript}", parse_mode="Markdown")
    await _run_agent_and_reply(msg, transcript)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages through the same agent pipeline."""
    await _run_agent_and_reply(update.message, update.message.text.strip())


async def _run_agent_and_reply(msg, transcript: str) -> None:
    git_sync.pull(VAULT_REPO_PATH)
    try:
        reply = await brain.process_transcript(transcript, VAULT_REPO_PATH)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        await msg.reply_text("❌ Could not process your message.")
        return
    git_sync.sync_write(VAULT_REPO_PATH, f"bot: {transcript[:60]}")
    await msg.reply_text(reply)
