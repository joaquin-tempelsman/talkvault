# tests/test_vault_operations.py
import subprocess
import pytest
from pathlib import Path


@pytest.fixture
def temp_git_repo(tmp_path):
    """Creates a real local git repo for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
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


def test_sync_write_commits_and_pushes(temp_git_repo):
    """sync_write commits changes (push skipped since no remote)."""
    from bot.vault.git_sync import sync_write
    note = temp_git_repo / "note.md"
    note.write_text("# Note")
    sync_write(str(temp_git_repo), "note: test")
    log = subprocess.run(["git", "log", "--oneline"], cwd=temp_git_repo, capture_output=True, text=True)
    assert "note: test" in log.stdout
