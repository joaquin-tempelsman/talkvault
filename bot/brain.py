# bot/brain.py
"""
LangChain 1.0 agent with LangGraph checkpointer for multi-turn vault operations.
Uses interrupt() for human-in-the-loop confirmation via Telegram.
"""
import logging

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from bot.config import OPENAI_API_KEY, FLOW_CONFIG
from bot.tools.registry import make_registry_tools
from bot.tools.notes import make_note_tools
from bot.tools.interaction import ask_user

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are TalkVault, a voice-controlled Obsidian vault assistant.
The user sends voice or text messages; you receive the transcription.

## Message Classification
Every message is either a COMMAND or a NOTE.

### COMMANDS
Commands modify the vault registry. Execute them immediately and confirm.
Examples:
- "add note group X" / "add note groups X, Y, Z"
- "add entity group X connected to note groups Y, Z"
- "add entities A, B, C to entity group X"
Batch operations are supported. After executing, confirm what was done.

### NOTES
Everything else is a note. Process notes in this exact order:

**Step 1: Detect Note Group (mode: {detect_note_group})**
Call list_note_groups() to see available groups. Analyze the note text.
- If mode is "guess": pick the best match and proceed to Step 2.
- If mode is "ask": call ask_user to propose your choice and wait for confirmation.

**Step 2: Detect Entities (mode: {detect_entities})**
Call get_entities_for_note_group() with the assigned note group.
Scan the note text for mentions of returned entities.
- If mode is "guess": assign detected entities and proceed to Step 3.
- If mode is "ask": call ask_user to propose entities and wait for confirmation.

**Step 3: Final Review (ALWAYS)**
You MUST call ask_user with a full summary before saving. Format:
"Note group: [group]
Entities: [entity1] ([group1]), [entity2] ([group2])
File: [NoteGroup]/[date]-[slug].md
Approve, modify, or cancel?"

NEVER call save_note without completing this final review step.
If the user wants to modify, update assignments and re-present the review.
If the user cancels, acknowledge and do not save.

**Step 4: Save**
Only after user approval, call save_note with all parameters.
Confirm the saved file path to the user.

## Important Rules
- Always follow steps in order: detect group -> detect entities -> final review -> save
- Never skip the final review step
- Keep responses concise (1-2 sentences for confirmations)
""".format(**FLOW_CONFIG)

# Module-level singleton
_agent = None


def get_agent(vault_path: str):
    """Get or create the agent singleton."""
    global _agent
    if _agent is not None:
        return _agent

    model = ChatOpenAI(
        model="gpt-4o",
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    tools = [
        *make_registry_tools(vault_path),
        *make_note_tools(vault_path),
        ask_user,
    ]

    _agent = create_agent(
        model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )

    logger.info("brain: agent initialized with %d tools", len(tools))
    return _agent
