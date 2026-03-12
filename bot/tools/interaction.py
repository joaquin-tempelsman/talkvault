# bot/tools/interaction.py
"""
Interaction tool using LangGraph interrupt for multi-turn conversations.
"""
from langchain.tools import tool
from langgraph.types import interrupt


@tool
def ask_user(question: str) -> str:
    """Ask the user a question and wait for their response.
    Use this to confirm note group, entities, or for final review before saving.
    The question will be sent to the user via Telegram and execution pauses
    until they reply."""
    return interrupt({"question": question})
