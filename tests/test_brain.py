# tests/test_brain.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ── Path safety tests ──────────────────────────────────────────────────────────

def test_safe_path_allows_vault_subpath(tmp_path):
    from bot.brain import _safe_path
    result = _safe_path(str(tmp_path), "Notes/meeting.md")
    assert result == (tmp_path / "Notes" / "meeting.md").resolve()


def test_safe_path_blocks_traversal(tmp_path):
    from bot.brain import _safe_path
    with pytest.raises(PermissionError):
        _safe_path(str(tmp_path), "../../etc/passwd")


def test_safe_path_blocks_absolute_outside(tmp_path):
    from bot.brain import _safe_path
    with pytest.raises(PermissionError):
        _safe_path(str(tmp_path), "/etc/passwd")


def test_safe_path_allows_absolute_inside_vault(tmp_path):
    from bot.brain import _safe_path
    # Absolute path that genuinely lives inside the vault should be allowed
    inside = str(tmp_path / "Notes" / "ok.md")
    result = _safe_path(str(tmp_path), inside)
    assert str(result).startswith(str(tmp_path.resolve()))


# ── Fallback tool tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_create_note(tmp_path):
    from bot.brain import _make_direct_tools
    tools = {t.name: t for t in _make_direct_tools(str(tmp_path))}
    result = tools["create_note"].invoke(
        {"path": "Notes/test.md", "content": "# Hello", "tags": "meeting,carlos"}
    )
    assert "Created" in result
    content = (tmp_path / "Notes" / "test.md").read_text()
    assert "# Hello" in content
    assert "tags:" in content
    assert "meeting" in content


@pytest.mark.asyncio
async def test_fallback_search_vault(tmp_path):
    from bot.brain import _make_direct_tools
    (tmp_path / "note1.md").write_text("marketing budget is 10k")
    (tmp_path / "note2.md").write_text("carlos call scheduled")
    tools = {t.name: t for t in _make_direct_tools(str(tmp_path))}
    result = tools["search_vault"].invoke({"query": "marketing budget"})
    assert "note1.md" in result
    assert "note2.md" not in result


@pytest.mark.asyncio
async def test_fallback_tool_blocks_traversal(tmp_path):
    from bot.brain import _make_direct_tools
    tools = {t.name: t for t in _make_direct_tools(str(tmp_path))}
    with pytest.raises(PermissionError):
        tools["create_note"].invoke(
            {"path": "../../evil.sh", "content": "rm -rf /"}
        )


# ── process_transcript routing tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_transcript_uses_mcp_primary(tmp_path):
    """Primary MCP agent succeeds — fallback never called."""
    with patch("bot.brain._run_mcp_agent", new_callable=AsyncMock) as mock_mcp, \
         patch("bot.brain._run_fallback_agent", new_callable=AsyncMock) as mock_fallback:
        mock_mcp.return_value = "Note created."
        from bot.brain import process_transcript
        reply = await process_transcript("add a note about Carlos", str(tmp_path))
    assert reply == "Note created."
    mock_mcp.assert_awaited_once()
    mock_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_transcript_falls_back_on_mcp_failure(tmp_path):
    """Primary MCP agent raises — fallback agent is called."""
    with patch("bot.brain._run_mcp_agent", new_callable=AsyncMock) as mock_mcp, \
         patch("bot.brain._run_fallback_agent", new_callable=AsyncMock) as mock_fallback:
        mock_mcp.side_effect = RuntimeError("npx not found")
        mock_fallback.return_value = "Done via fallback."
        from bot.brain import process_transcript
        reply = await process_transcript("add a note about Carlos", str(tmp_path))
    assert reply == "Done via fallback."
    mock_fallback.assert_awaited_once()
