# TalkVault

## Objective

Voice-first personal knowledge base in Obsidian. Send voice or text messages via Telegram, and the system classifies, tags, and stores notes automatically. Browse from Obsidian on desktop — everything is synced via git.

## Components

- **Telegram** — mobile interface (voice + text)
- **Telegram bot** (DigitalOcean) — orchestrator: transcribes audio (Whisper API), passes text to LLM agent
- **LLM agent** (LangChain 1.0 + GPT-4o) — classifies messages, detects note groups and entities, confirms with user, saves notes
- **Vault** (git repo) — Obsidian vault with structured `_meta/` registry for note groups and entity groups
- **Git + GitHub** — sync layer. Bot pulls before reads, commits+pushes after writes. GitHub is single source of truth.
- **Obsidian** (desktop) — reading and exploration layer

## Core Concepts

### Note Groups
Categories for notes (e.g., Personal, Ideas, Work). Each note belongs to one group. Stored as `_meta/note_groups/{name}.md`. Each group has a corresponding vault folder.

### Entity Groups
Collections of entities connected to specific note groups (e.g., "friends" connected to Personal and Work). Stored as `_meta/entity_groups/{name}.md`.

### Entities
Individual items within entity groups (e.g., Carlos, Ana in "friends"). When a note mentions a known entity from a connected entity group, it gets tagged.

## Message Flow

A message is either a **command** or a **note**.

### Commands
Registry operations — execute and inform:
- `add note group X` / `add note groups X, Y, Z`
- `add entity group X connected to Y, Z`
- `add entities A, B, C to entity group X`

### Notes
Processed through a configurable pipeline:

1. **Detect note group** (mode: ask | guess) — agent reads available groups, picks best match
2. **Detect entities** (mode: ask | guess) — agent loads entities from connected entity groups, scans note
3. **Final review** (always) — agent presents summary: note group, entities, file path. User approves/modifies/cancels
4. **Save** — write note with frontmatter, git commit + push

Each step's mode is tunable:
```python
FLOW_CONFIG = {
    "detect_note_group": "guess",
    "detect_entities": "ask",
}
```

## Vault Structure

```
vault/
├── _meta/
│   ├── note_groups/
│   │   ├── personal.md
│   │   └── work.md
│   ├── entity_groups/
│   │   ├── friends.md       # connected_note_groups: [Personal, Work], entities: [Carlos, Ana]
│   │   └── places.md
├── Personal/
│   └── 2026-03-11-walk-in-park.md
└── Work/
    └── 2026-03-11-meeting-carlos.md
```

### Note Frontmatter

```yaml
---
note_group: Personal
entities:
  - Carlos
entity_groups:
  - friends
date: 2026-03-11
---
```

## Technical Architecture

- **Agent**: LangChain 1.0 `create_agent` with custom `@tool` functions (no MCP)
- **Multi-turn**: LangGraph `interrupt()` / `Command(resume=...)` with `InMemorySaver` checkpointer
- **Telegram**: Polling mode (no webhook/nginx needed)
- **Infra**: Docker on DigitalOcean, CI/CD via GitHub Actions

Full spec: `docs/superpowers/specs/2026-03-11-talkvault-v2-design.md`
