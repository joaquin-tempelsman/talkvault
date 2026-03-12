# bot/tools/registry.py
"""
Registry tools for managing note groups and entity groups in the vault.
All operations read/write _meta/ files with YAML frontmatter.
"""
import re
from pathlib import Path

from langchain.tools import tool


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown file content."""
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).strip().splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        # Parse YAML-style lists: [A, B, C]
        if val.startswith("[") and val.endswith("]"):
            result[key] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        else:
            result[key] = val
    return result


def _write_frontmatter(data: dict) -> str:
    """Build YAML frontmatter string from dict."""
    lines = ["---"]
    for key, val in data.items():
        if isinstance(val, list):
            lines.append(f"{key}: [{', '.join(val)}]")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---\n")
    return "\n".join(lines)


def make_registry_tools(vault_path: str) -> list:
    """Create registry tools scoped to vault_path."""
    vault = Path(vault_path)
    meta = vault / "_meta"

    @tool
    def list_note_groups() -> str:
        """List all available note groups from the vault registry."""
        ng_dir = meta / "note_groups"
        if not ng_dir.exists():
            return "No note groups found. Registry not initialized."
        groups = []
        for f in sorted(ng_dir.glob("*.md")):
            fm = _parse_frontmatter(f.read_text(encoding="utf-8"))
            groups.append(fm.get("name", f.stem))
        if not groups:
            return "No note groups defined yet."
        return "Note groups: " + ", ".join(groups)

    @tool
    def add_note_group(name: str) -> str:
        """Add a new note group. Creates the registry file and vault folder."""
        ng_dir = meta / "note_groups"
        ng_dir.mkdir(parents=True, exist_ok=True)
        slug = name.lower().replace(" ", "-")
        filepath = ng_dir / f"{slug}.md"
        if filepath.exists():
            return f"Note group '{name}' already exists."
        filepath.write_text(
            _write_frontmatter({"type": "note_group", "name": name}),
            encoding="utf-8",
        )
        # Create the vault folder for this note group
        (vault / name).mkdir(parents=True, exist_ok=True)
        return f"Created note group '{name}'."

    @tool
    def list_entity_groups() -> str:
        """List all entity groups with their connected note groups and entities."""
        eg_dir = meta / "entity_groups"
        if not eg_dir.exists():
            return "No entity groups found."
        results = []
        for f in sorted(eg_dir.glob("*.md")):
            fm = _parse_frontmatter(f.read_text(encoding="utf-8"))
            name = f.stem
            connected = fm.get("connected_note_groups", [])
            entities = fm.get("entities", [])
            results.append(
                f"- {name}: connected to [{', '.join(connected)}], "
                f"entities: [{', '.join(entities)}]"
            )
        if not results:
            return "No entity groups defined yet."
        return "Entity groups:\n" + "\n".join(results)

    @tool
    def add_entity_group(name: str, connected_note_groups: list[str]) -> str:
        """Add a new entity group connected to specified note groups."""
        eg_dir = meta / "entity_groups"
        eg_dir.mkdir(parents=True, exist_ok=True)
        slug = name.lower().replace(" ", "-")
        filepath = eg_dir / f"{slug}.md"
        if filepath.exists():
            return f"Entity group '{name}' already exists."
        filepath.write_text(
            _write_frontmatter({
                "type": "entity_group",
                "connected_note_groups": connected_note_groups,
                "entities": [],
            }),
            encoding="utf-8",
        )
        return f"Created entity group '{name}' connected to [{', '.join(connected_note_groups)}]."

    @tool
    def add_entities_to_group(group_name: str, entities: list[str]) -> str:
        """Add one or more entities to an existing entity group."""
        eg_dir = meta / "entity_groups"
        slug = group_name.lower().replace(" ", "-")
        filepath = eg_dir / f"{slug}.md"
        if not filepath.exists():
            return f"Entity group '{group_name}' not found."
        text = filepath.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        existing = fm.get("entities", [])
        added = []
        for e in entities:
            if e not in existing:
                existing.append(e)
                added.append(e)
        fm["entities"] = existing
        filepath.write_text(_write_frontmatter(fm), encoding="utf-8")
        if not added:
            return f"All entities already exist in '{group_name}'."
        return f"Added [{', '.join(added)}] to '{group_name}'."

    @tool
    def get_entities_for_note_group(note_group: str) -> str:
        """Get all entities from entity groups connected to the given note group.
        Returns entity groups and their entities for matching against note content."""
        eg_dir = meta / "entity_groups"
        if not eg_dir.exists():
            return "No entity groups found."
        results = {}
        for f in sorted(eg_dir.glob("*.md")):
            fm = _parse_frontmatter(f.read_text(encoding="utf-8"))
            connected = fm.get("connected_note_groups", [])
            if note_group in connected:
                entities = fm.get("entities", [])
                if entities:
                    results[f.stem] = entities
        if not results:
            return f"No entity groups connected to '{note_group}'."
        parts = []
        for group, ents in results.items():
            parts.append(f"{group}: [{', '.join(ents)}]")
        return "Connected entities:\n" + "\n".join(parts)

    return [
        list_note_groups,
        add_note_group,
        list_entity_groups,
        add_entity_group,
        add_entities_to_group,
        get_entities_for_note_group,
    ]
