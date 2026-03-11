# tests/test_vault_operations.py
import subprocess, tempfile, os, pytest
from pathlib import Path


@pytest.fixture
def temp_git_repo(tmp_path):
    """Creates a real local git repo for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    # Initial commit so HEAD exists
    (tmp_path / "README.md").write_text("vault")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_commit_new_file(temp_git_repo):
    from bot.vault.git_sync import commit_changes
    note = temp_git_repo / "test_note.md"
    note.write_text("# Test\ncontent here")
    commit_changes(str(temp_git_repo), "test: add note via bot")
    log = subprocess.run(["git", "log", "--oneline"], cwd=temp_git_repo, capture_output=True, text=True)
    assert "test: add note via bot" in log.stdout


@pytest.mark.asyncio
async def test_create_note_direct(temp_git_repo):
    """Tests direct Python fallback (no MCP needed)."""
    from bot.vault.operations import create_note_direct
    path = str(temp_git_repo / "Notes" / "meeting.md")
    await create_note_direct(path, "# Meeting\nNotes here", ["meeting", "carlos"])
    content = Path(path).read_text()
    assert "# Meeting" in content
    assert "tags:" in content  # frontmatter injected
    assert "meeting" in content


@pytest.mark.asyncio
async def test_search_vault_direct(temp_git_repo):
    from bot.vault.operations import search_vault_direct
    (temp_git_repo / "note1.md").write_text("# Budget\nmarketing budget is 10k")
    (temp_git_repo / "note2.md").write_text("# Meeting\nCarlos call")
    results = await search_vault_direct(str(temp_git_repo), "marketing budget")
    assert any("note1.md" in r for r in results)
