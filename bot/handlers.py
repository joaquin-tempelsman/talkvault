# bot/handlers.py
import io
import logging
import time

from telegram import Update
from telegram.ext import ContextTypes
from langgraph.types import Command

from bot.config import VAULT_REPO_PATH, SESSION_TIMEOUT
from bot.brain import get_agent
from bot.vault import git_sync

logger = logging.getLogger(__name__)

# Active sessions: user_id → {"thread_id": str, "last_active": float}
_sessions: dict[int, dict] = {}


def _has_active_session(user_id: int) -> bool:
    """Check if user has an active (non-expired) session."""
    session = _sessions.get(user_id)
    if session is None:
        return False
    if time.time() - session["last_active"] > SESSION_TIMEOUT:
        del _sessions[user_id]
        return False
    return True


def _extract_reply(result) -> str:
    """Extract the text reply from agent result."""
    if hasattr(result, "value"):
        # GraphOutput from version="v2"
        msgs = result.value.get("messages", [])
    elif isinstance(result, dict):
        msgs = result.get("messages", [])
    else:
        return str(result)

    if msgs:
        last = msgs[-1]
        if hasattr(last, "content"):
            return last.content
        if isinstance(last, dict):
            return last.get("content", str(last))
    return "Done."


def _extract_interrupt_question(result) -> str | None:
    """Extract the question from an interrupt, if present."""
    interrupts = None
    if hasattr(result, "interrupts") and result.interrupts:
        interrupts = result.interrupts
    elif isinstance(result, dict) and "__interrupt__" in result:
        interrupts = result["__interrupt__"]

    if not interrupts:
        return None

    # Get the interrupt value (could be list or single)
    interrupt_data = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
    value = interrupt_data.value if hasattr(interrupt_data, "value") else interrupt_data
    if isinstance(value, dict):
        return value.get("question", str(value))
    return str(value)


async def _run_agent(user_id: int, text: str, is_resume: bool = False) -> tuple[str | None, str | None]:
    """
    Run the agent. Returns (reply, interrupt_question).
    If interrupt_question is set, the agent is paused and waiting for user input.
    """
    agent = get_agent(VAULT_REPO_PATH)
    config = {"configurable": {"thread_id": str(user_id)}}

    if is_resume:
        result = await agent.ainvoke(Command(resume=text), config=config, version="v2")
    else:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": text}]},
            config=config,
            version="v2",
        )

    question = _extract_interrupt_question(result)
    if question:
        return None, question

    reply = _extract_reply(result)
    return reply, None


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pipeline: voice → transcribe → agent → reply (with interrupt support)."""
    from bot import transcriber

    msg = update.message
    user_id = msg.from_user.id
    await msg.reply_text("Transcribing...")

    voice_file = await context.bot.get_file(msg.voice.file_id)
    audio_buffer = io.BytesIO()
    await voice_file.download_to_memory(audio_buffer)

    try:
        transcript = await transcriber.transcribe_audio_bytes(audio_buffer.getvalue())
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        await msg.reply_text("Transcription failed. Please try again.")
        return

    await msg.reply_text(f"Transcript: {transcript}")
    await _process_message(msg, user_id, transcript)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages — either a new message or a reply to an interrupt."""
    msg = update.message
    user_id = msg.from_user.id
    text = msg.text.strip()

    if _has_active_session(user_id):
        # Resume existing session
        await _process_message(msg, user_id, text, is_resume=True)
    else:
        # New message
        await _process_message(msg, user_id, text)


async def _process_message(msg, user_id: int, text: str, is_resume: bool = False) -> None:
    """Process a message through the agent, handling interrupts."""
    if not is_resume:
        git_sync.pull(VAULT_REPO_PATH)

    try:
        reply, question = await _run_agent(user_id, text, is_resume=is_resume)
    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        _sessions.pop(user_id, None)
        await msg.reply_text("Could not process your message.")
        return

    if question:
        # Agent is paused, waiting for user input
        _sessions[user_id] = {"thread_id": str(user_id), "last_active": time.time()}
        await msg.reply_text(question)
    else:
        # Agent completed
        _sessions.pop(user_id, None)
        await msg.reply_text(reply or "Done.")
