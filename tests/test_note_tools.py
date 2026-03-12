# tests/test_note_tools.py
import re
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from bot.tools.notes import make_note_tools


class TestSaveNote:
    @patch("bot.tools.notes.sync_write")
    def test_creates_note_with_frontmatter(self, mock_sync, seeded_vault):
        tools = make_note_tools(seeded_vault)
        save = tools[0]  # save_note
        result = save.invoke({
            "note_group": "Personal",
            "content": "Went to the park and saw Carlos.",
            "entities": ["Carlos"],
            "entity_groups": ["friends"],
            "slug": "walk-in-park",
        })
        assert "Saved note to Personal/" in result

        # Find the created file
        personal_dir = Path(seeded_vault) / "Personal"
        notes = list(personal_dir.glob("*walk-in-park.md"))
        assert len(notes) == 1

        content = notes[0].read_text(encoding="utf-8")
        assert "note_group: Personal" in content
        assert "  - Carlos" in content
        assert "  - friends" in content
        assert "Went to the park" in content

        mock_sync.assert_called_once()

    @patch("bot.tools.notes.sync_write")
    def test_creates_directory_if_missing(self, mock_sync, vault_path):
        tools = make_note_tools(vault_path)
        save = tools[0]
        result = save.invoke({
            "note_group": "NewGroup",
            "content": "Test content",
            "entities": [],
            "entity_groups": [],
            "slug": "test-note",
        })
        assert "Saved" in result
        assert (Path(vault_path) / "NewGroup").is_dir()


class TestSearchVault:
    def test_finds_matching_notes(self, seeded_vault):
        # Create a note to search for
        vault = Path(seeded_vault)
        (vault / "Personal").mkdir(exist_ok=True)
        (vault / "Personal" / "test.md").write_text("Meeting with Carlos about launch", encoding="utf-8")

        tools = make_note_tools(seeded_vault)
        search = tools[1]  # search_vault
        result = search.invoke({"query": "Carlos"})
        assert "Personal/test.md" in result

    def test_no_results(self, seeded_vault):
        tools = make_note_tools(seeded_vault)
        search = tools[1]
        result = search.invoke({"query": "nonexistent_xyz"})
        assert "No notes found" in result

    def test_skips_meta_files(self, seeded_vault):
        tools = make_note_tools(seeded_vault)
        search = tools[1]
        # _meta files contain "Personal" but should not appear in results
        result = search.invoke({"query": "note_group"})
        assert "_meta" not in result


class TestReadNote:
    def test_reads_existing_note(self, seeded_vault):
        vault = Path(seeded_vault)
        (vault / "Personal" / "test.md").write_text("Hello world", encoding="utf-8")
        tools = make_note_tools(seeded_vault)
        read = tools[2]  # read_note
        result = read.invoke({"path": "Personal/test.md"})
        assert "Hello world" in result

    def test_missing_note(self, seeded_vault):
        tools = make_note_tools(seeded_vault)
        read = tools[2]
        result = read.invoke({"path": "nonexistent.md"})
        assert "not found" in result
