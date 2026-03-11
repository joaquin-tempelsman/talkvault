# bot/brain.py
"""
Two-agent brain:
  Primary  — LangChain agent with obsidian-mcp tools (MCP subprocess).
  Fallback — LangChain agent with @tool-decorated direct filesystem ops.

Both agents are hard-restricted to vault_path via _safe_path().
"""
import logging
from pathlib import Path
from datetime import datetime

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from bot.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a voice-controlled Obsidian vault assistant. "
    "The user sends voice messages; you receive the transcription. "
    "Decide what vault operation(s) to perform and call the appropriate tool(s). "
    "Use descriptive relative paths like 'Meetings/carlos-launch.md' or 'Ideas/product-idea.md'. "
    "After using tools, give a short confirmation reply (1-2 sentences)."
)


# ── Path safety ────────────────────────────────────────────────────────────────

def _safe_path(vault_path: str, user_path: str) -> Path:
    """
    Resolve user_path and verify it stays inside vault_path.
    - Relative paths are resolved relative to vault_path.
    - Absolute paths are only permitted if they already reside inside vault_path.
    Raises PermissionError on any traversal or out-of-vault attempt.
    """
    vault = Path(vault_path).resolve()
    p = Path(user_path)
    target = p.resolve() if p.is_absolute() else (vault / user_path).resolve()
    if target != vault and not str(target).startswith(str(vault) + "/"):
        raise PermissionError(
            f"Path '{user_path}' resolves outside vault root '{vault}'"
        )
    return target


# ── Fallback tools factory ─────────────────────────────────────────────────────

def _make_direct_tools(vault_path: str) -> list:
    """
    Return a list of @tool-decorated functions scoped to vault_path.
    All file I/O is guarded by _safe_path — nothing outside vault_path
    can be read or written.
    """

    @tool
    def create_note(path: str, content: str, tags: str = "") -> str:
        """Create a new markdown note in the vault. path is relative to vault root."""
        target = _safe_path(vault_path, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        frontmatter = ""
        if tag_list:
            date = datetime.now().strftime("%Y-%m-%d")
            frontmatter = f"---\ntags: [{', '.join(tag_list)}]\ncreated: {date}\n---\n\n"
        target.write_text(frontmatter + content, encoding="utf-8")
        return f"Created note at {path}"

    @tool
    def append_to_note(path: str, content: str) -> str:
        """Append content to an existing note in the vault. path is relative to vault root."""
        target = _safe_path(vault_path, path)
        if not target.exists():
            return f"Note not found: {path}"
        existing = target.read_text(encoding="utf-8")
        target.write_text(existing + "\n\n" + content, encoding="utf-8")
        return f"Appended to {path}"

    @tool
    def read_note(path: str) -> str:
        """Read the full contents of a note. path is relative to vault root."""
        target = _safe_path(vault_path, path)
        if not target.exists():
            return f"Note not found: {path}"
        return target.read_text(encoding="utf-8")

    @tool
    def search_vault(query: str) -> str:
        """Search all markdown notes in the vault for a keyword or phrase."""
        vault = Path(vault_path).resolve()
        matches = []
        for md_file in vault.rglob("*.md"):
            try:
                if query.lower() in md_file.read_text(encoding="utf-8").lower():
                    matches.append(str(md_file.relative_to(vault)))
            except Exception:
                pass
        if not matches:
            return f"No notes found matching '{query}'"
        return "Found in:\n" + "\n".join(f"- {m}" for m in matches[:20])

    @tool
    def list_notes(directory: str = "") -> str:
        """List all markdown notes in the vault, optionally within a subdirectory."""
        vault = Path(vault_path).resolve()
        base = _safe_path(vault_path, directory) if directory else vault
        if not base.exists():
            return f"Directory not found: {directory}"
        notes = [str(p.relative_to(vault)) for p in base.rglob("*.md")]
        if not notes:
            return "No notes found"
        return "\n".join(f"- {n}" for n in notes[:50])

    return [create_note, append_to_note, read_note, search_vault, list_notes]


# ── Primary agent (MCP) ────────────────────────────────────────────────────────

async def _run_mcp_agent(transcript: str, vault_path: str, model: ChatOpenAI) -> str:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({
        "obsidian": {
            "transport": "stdio",
            "command": "npx",
            "args": ["@modelcontextprotocol/server-filesystem", vault_path],
        }
    })
    tools = await client.get_tools()
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": transcript}]}
    )
    return result["messages"][-1].content


# ── Fallback agent (direct filesystem) ────────────────────────────────────────

async def _run_fallback_agent(transcript: str, vault_path: str, model: ChatOpenAI) -> str:
    tools = _make_direct_tools(vault_path)
    agent = create_agent(model, tools, system_prompt=SYSTEM_PROMPT)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": transcript}]}
    )
    return result["messages"][-1].content


# ── Public entry point ─────────────────────────────────────────────────────────

async def process_transcript(transcript: str, vault_path: str) -> str:
    """
    Route transcript through the two-agent pipeline:
      1. Primary: LangChain agent + obsidian-mcp tools (scoped to vault_path)
      2. Fallback: LangChain agent + direct @tool filesystem ops (scoped to vault_path)
    Returns the agent's final reply string.
    """
    model = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY, temperature=0)

    try:
        reply = await _run_mcp_agent(transcript, vault_path, model)
        logger.info("brain: primary MCP agent handled request")
        return reply
    except Exception as e:
        logger.warning(f"brain: MCP agent failed ({e}), switching to fallback agent")

    reply = await _run_fallback_agent(transcript, vault_path, model)
    logger.info("brain: fallback direct-filesystem agent handled request")
    return reply
