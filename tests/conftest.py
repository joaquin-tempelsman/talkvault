# tests/conftest.py
import os
import pytest
from pathlib import Path

pytest_asyncio_mode = "auto"


@pytest.fixture
def vault_path(tmp_path):
    """Create a temporary vault with _meta structure."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "_meta" / "note_groups").mkdir(parents=True)
    (vault / "_meta" / "entity_groups").mkdir(parents=True)
    return str(vault)


@pytest.fixture
def seeded_vault(vault_path):
    """Vault with pre-seeded note groups and entity groups."""
    vault = Path(vault_path)

    # Note groups
    (vault / "_meta" / "note_groups" / "personal.md").write_text(
        "---\ntype: note_group\nname: Personal\n---\n", encoding="utf-8"
    )
    (vault / "_meta" / "note_groups" / "work.md").write_text(
        "---\ntype: note_group\nname: Work\n---\n", encoding="utf-8"
    )
    (vault / "Personal").mkdir(exist_ok=True)
    (vault / "Work").mkdir(exist_ok=True)

    # Entity groups
    (vault / "_meta" / "entity_groups" / "friends.md").write_text(
        "---\ntype: entity_group\nconnected_note_groups: [Personal, Work]\nentities: [Carlos, Ana]\n---\n",
        encoding="utf-8",
    )
    (vault / "_meta" / "entity_groups" / "places.md").write_text(
        "---\ntype: entity_group\nconnected_note_groups: [Personal]\nentities: [Central Park, Office]\n---\n",
        encoding="utf-8",
    )

    return vault_path
