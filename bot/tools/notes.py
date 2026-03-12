# bot/tools/notes.py
"""
Note tools for saving, reading, and searching notes in the vault.
"""
import re
from datetime import datetime
from pathlib import Path

from langchain.tools import tool

from bot.vault.git_sync import sync_write


def make_note_tools(vault_path: str) -> list:
    """Create note tools scoped to vault_path."""
    vault = Path(vault_path)

    @tool
    def save_note(
        note_group: str,
        content: str,
        entities: list[str],
        entity_groups: list[str],
        slug: str,
    ) -> str:
        """Save a note to the vault with frontmatter. Call ONLY after final user approval.
        Args:
            note_group: The note group (folder name)
            content: The note body text
            entities: List of entity names to tag
            entity_groups: List of entity group names connected
            slug: Short kebab-case identifier for the filename
        """
        date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date}-{slug}.md"
        note_dir = vault / note_group
        note_dir.mkdir(parents=True, exist_ok=True)
        filepath = note_dir / filename

        # Build frontmatter
        lines = ["---"]
        lines.append(f"note_group: {note_group}")
        if entities:
            lines.append("entities:")
            for e in entities:
                lines.append(f"  - {e}")
        if entity_groups:
            lines.append("entity_groups:")
            for eg in entity_groups:
                lines.append(f"  - {eg}")
        lines.append(f"date: {date}")
        lines.append("---")
        lines.append("")
        lines.append(content)

        filepath.write_text("\n".join(lines), encoding="utf-8")

        # Git commit + push
        sync_write(vault_path, f"note: {slug} [{note_group}]")

        return f"Saved note to {note_group}/{filename}"

    @tool
    def search_vault(query: str) -> str:
        """Search all markdown notes in the vault for a keyword or phrase."""
        matches = []
        for md_file in vault.rglob("*.md"):
            # Skip _meta files
            if "_meta" in md_file.parts:
                continue
            try:
                if re.search(query, md_file.read_text(encoding="utf-8"), re.IGNORECASE):
                    matches.append(str(md_file.relative_to(vault)))
            except Exception:
                pass
        if not matches:
            return f"No notes found matching '{query}'."
        return "Found in:\n" + "\n".join(f"- {m}" for m in matches[:20])

    @tool
    def read_note(path: str) -> str:
        """Read the full contents of a note. Path is relative to vault root."""
        target = vault / path
        if not target.exists():
            return f"Note not found: {path}"
        # Path safety check
        if not str(target.resolve()).startswith(str(vault.resolve())):
            return "Access denied: path outside vault."
        return target.read_text(encoding="utf-8")

    return [save_note, search_vault, read_note]
