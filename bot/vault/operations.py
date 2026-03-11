# bot/vault/operations.py
"""
Vault operations: MCP-first with Python fallback.
MCP uses @modelcontextprotocol/server-filesystem subprocess.
"""
import asyncio
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── MCP client (lazy-initialized) ─────────────────────────────────────────────

_mcp_session = None  # module-level session, initialized once


async def _get_mcp_session(vault_path: str):
    """Return a live MCP session, or None if MCP unavailable."""
    global _mcp_session
    if _mcp_session is not None:
        return _mcp_session
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(
            command="npx",
            args=["@modelcontextprotocol/server-filesystem", vault_path],
        )
        read, write = await stdio_client(params).__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()
        _mcp_session = session
        logger.info("MCP filesystem server connected")
        return _mcp_session
    except Exception as e:
        logger.warning(f"MCP unavailable, using Python fallback: {e}")
        return None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_frontmatter(tags: list[str]) -> str:
    if not tags:
        return ""
    tags_str = ", ".join(tags)
    date = datetime.now().strftime("%Y-%m-%d")
    return f"---\ntags: [{tags_str}]\ncreated: {date}\n---\n\n"


# ── MCP implementations ────────────────────────────────────────────────────────

async def _mcp_read_file(session, path: str) -> str:
    result = await session.call_tool("read_file", {"path": path})
    return result.content[0].text


async def _mcp_write_file(session, path: str, content: str) -> None:
    await session.call_tool("write_file", {"path": path, "content": content})


async def _mcp_list_directory(session, path: str) -> list[str]:
    result = await session.call_tool("list_directory", {"path": path})
    return [item.name for item in result.content]


async def _mcp_search_files(session, path: str, pattern: str) -> list[str]:
    result = await session.call_tool("search_files", {"path": path, "pattern": pattern})
    return [item.text for item in result.content]


# ── Python fallbacks ───────────────────────────────────────────────────────────

async def create_note_direct(path: str, content: str, tags: list[str] = []) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    full_content = _build_frontmatter(tags) + content
    p.write_text(full_content, encoding="utf-8")


async def append_to_note_direct(path: str, content: str) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Note not found: {path}")
    existing = p.read_text(encoding="utf-8")
    p.write_text(existing + "\n\n" + content, encoding="utf-8")


async def read_note_direct(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


async def search_vault_direct(vault_path: str, query: str) -> list[str]:
    results = []
    for md_file in Path(vault_path).rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            if re.search(query, text, re.IGNORECASE):
                results.append(str(md_file))
        except Exception:
            pass
    return results


async def list_notes_direct(vault_path: str, directory: str = "") -> list[str]:
    base = Path(vault_path) / directory
    if not base.exists():
        return []
    return [str(p.relative_to(vault_path)) for p in base.rglob("*.md")]


# ── Public API (MCP-first, fallback to direct) ─────────────────────────────────

async def create_note(vault_path: str, path: str, content: str, tags: list[str] = []) -> None:
    full_path = str(Path(vault_path) / path) if not path.startswith("/") else path
    session = await _get_mcp_session(vault_path)
    if session:
        try:
            full_content = _build_frontmatter(tags) + content
            # Ensure parent dir exists via MCP
            parent = str(Path(full_path).parent)
            await session.call_tool("create_directory", {"path": parent})
            await _mcp_write_file(session, full_path, full_content)
            return
        except Exception as e:
            logger.warning(f"MCP create_note failed, using Python fallback: {e}")
    await create_note_direct(full_path, content, tags)


async def append_to_note(vault_path: str, path: str, content: str) -> None:
    full_path = str(Path(vault_path) / path) if not path.startswith("/") else path
    session = await _get_mcp_session(vault_path)
    if session:
        try:
            existing = await _mcp_read_file(session, full_path)
            await _mcp_write_file(session, full_path, existing + "\n\n" + content)
            return
        except Exception as e:
            logger.warning(f"MCP append failed, using Python fallback: {e}")
    await append_to_note_direct(full_path, content)


async def read_note(vault_path: str, path: str) -> str:
    full_path = str(Path(vault_path) / path) if not path.startswith("/") else path
    session = await _get_mcp_session(vault_path)
    if session:
        try:
            return await _mcp_read_file(session, full_path)
        except Exception as e:
            logger.warning(f"MCP read_note failed, using Python fallback: {e}")
    return await read_note_direct(full_path)


async def search_vault(vault_path: str, query: str) -> list[str]:
    session = await _get_mcp_session(vault_path)
    if session:
        try:
            return await _mcp_search_files(session, vault_path, query)
        except Exception as e:
            logger.warning(f"MCP search failed, using Python fallback: {e}")
    return await search_vault_direct(vault_path, query)


async def list_notes(vault_path: str, directory: str = "") -> list[str]:
    session = await _get_mcp_session(vault_path)
    if session:
        try:
            base = str(Path(vault_path) / directory) if directory else vault_path
            return await _mcp_list_directory(session, base)
        except Exception as e:
            logger.warning(f"MCP list failed, using Python fallback: {e}")
    return await list_notes_direct(vault_path, directory)
