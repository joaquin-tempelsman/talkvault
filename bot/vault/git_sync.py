# bot/vault/git_sync.py
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _run(cmd: list[str], cwd: str) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {cmd[1]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def pull(vault_path: str) -> None:
    """Pull latest changes. Skips if no remote configured."""
    try:
        _run(["git", "pull", "--ff-only"], cwd=vault_path)
        logger.info("vault: pulled latest changes")
    except RuntimeError as e:
        if "no tracking information" in str(e) or "no remote" in str(e).lower():
            logger.debug("vault: no remote, skipping pull")
        else:
            raise


def commit_changes(vault_path: str, message: str) -> None:
    """Stage all changes, commit. Does not push (push is separate)."""
    _run(["git", "add", "-A"], cwd=vault_path)
    # Check if there's anything to commit
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=vault_path
    )
    if status.returncode == 0:
        logger.debug("vault: nothing to commit")
        return
    _run(["git", "commit", "-m", message], cwd=vault_path)
    logger.info(f"vault: committed '{message}'")


def push(vault_path: str) -> None:
    """Push to remote. Skips if no remote configured."""
    try:
        _run(["git", "push"], cwd=vault_path)
        logger.info("vault: pushed to remote")
    except RuntimeError as e:
        err = str(e).lower()
        if "no remote" in err or "does not appear to be a git repository" in err or "no configured push destination" in err:
            logger.debug("vault: no remote, skipping push")
        else:
            raise


def pull_and_push_after(vault_path: str, message: str) -> None:
    """Pull, then after caller writes files, commit and push."""
    pull(vault_path)


def sync_write(vault_path: str, message: str) -> None:
    """Commit and push after a write operation."""
    commit_changes(vault_path, message)
    push(vault_path)
