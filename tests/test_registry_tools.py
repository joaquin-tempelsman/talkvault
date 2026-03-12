# tests/test_registry_tools.py
from pathlib import Path
from bot.tools.registry import make_registry_tools


class TestListNoteGroups:
    def test_empty_registry(self, vault_path):
        tools = make_registry_tools(vault_path)
        list_ng = tools[0]  # list_note_groups
        result = list_ng.invoke({})
        assert "No note groups" in result

    def test_with_groups(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        list_ng = tools[0]
        result = list_ng.invoke({})
        assert "Personal" in result
        assert "Work" in result


class TestAddNoteGroup:
    def test_creates_file_and_folder(self, vault_path):
        tools = make_registry_tools(vault_path)
        add_ng = tools[1]  # add_note_group
        result = add_ng.invoke({"name": "Ideas"})
        assert "Created" in result
        assert (Path(vault_path) / "_meta" / "note_groups" / "ideas.md").exists()
        assert (Path(vault_path) / "Ideas").is_dir()

    def test_duplicate_rejected(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        add_ng = tools[1]
        result = add_ng.invoke({"name": "Personal"})
        assert "already exists" in result


class TestAddEntityGroup:
    def test_creates_entity_group(self, vault_path):
        tools = make_registry_tools(vault_path)
        add_eg = tools[3]  # add_entity_group
        result = add_eg.invoke({"name": "books", "connected_note_groups": ["Personal", "Work"]})
        assert "Created" in result
        filepath = Path(vault_path) / "_meta" / "entity_groups" / "books.md"
        assert filepath.exists()
        content = filepath.read_text()
        assert "Personal" in content
        assert "Work" in content


class TestAddEntitiesToGroup:
    def test_adds_entities(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        add_ents = tools[4]  # add_entities_to_group
        result = add_ents.invoke({"group_name": "friends", "entities": ["David", "Elena"]})
        assert "David" in result
        assert "Elena" in result
        content = (Path(seeded_vault) / "_meta" / "entity_groups" / "friends.md").read_text()
        assert "David" in content
        assert "Elena" in content

    def test_skips_duplicates(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        add_ents = tools[4]
        result = add_ents.invoke({"group_name": "friends", "entities": ["Carlos"]})
        assert "already exist" in result

    def test_nonexistent_group(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        add_ents = tools[4]
        result = add_ents.invoke({"group_name": "nonexistent", "entities": ["X"]})
        assert "not found" in result


class TestGetEntitiesForNoteGroup:
    def test_returns_connected_entities(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        get_ents = tools[5]  # get_entities_for_note_group
        result = get_ents.invoke({"note_group": "Personal"})
        assert "friends" in result
        assert "Carlos" in result
        assert "Ana" in result
        assert "places" in result
        assert "Central Park" in result

    def test_filters_by_connection(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        get_ents = tools[5]
        result = get_ents.invoke({"note_group": "Work"})
        assert "friends" in result
        assert "Carlos" in result
        # places is only connected to Personal, not Work
        assert "places" not in result

    def test_no_connections(self, seeded_vault):
        tools = make_registry_tools(seeded_vault)
        # Add a note group with no entity groups connected
        tools[1].invoke({"name": "Ideas"})
        get_ents = tools[5]
        result = get_ents.invoke({"note_group": "Ideas"})
        assert "No entity groups connected" in result
