# TalkVault v2: Note Groups, Entities & Infrastructure

## Context

TalkVault is a voice-first Obsidian vault assistant. The current implementation (`bot/brain.py`) is a generic vault assistant that creates/reads/searches notes via a LangChain agent. The user wants to add structured note classification (note groups), entity detection (friends, books, places, etc.), and a configurable multi-turn flow where the agent classifies, tags, confirms with the user, then saves. Infrastructure should be adapted from the zenith project for DigitalOcean deployment.

## Decisions Made

- **Architecture**: Single LangChain 1.0 agent with tools (Approach A)
- **Storage**: All registry data inside the vault as Obsidian markdown (`_meta/` folder)
- **Vault layout**: Flat with note group as folder (`Personal/2026-03-11-walk-in-park.md`)
- **Multi-turn**: LangGraph `interrupt()` / `Command(resume=...)` with `InMemorySaver` checkpointer
- **Flow config**: Per-step `ask`/`guess` hardcoded in bot config, final review always required
- **Commands**: Execute and inform (no confirmation needed)
- **Telegram mode**: Polling (no webhook, no nginx, no ngrok, no domain needed)
- **No MCP/Node.js**: All vault operations are pure Python `@tool` functions

## 1. Vault Structure

```
vault/
├── _meta/
│   ├── note_groups/
│   │   ├── personal.md          # ---\n type: note_group\n name: Personal\n ---
│   │   ├── ideas.md
│   │   └── work.md
│   ├── entity_groups/
│   │   ├── friends.md           # ---\n type: entity_group\n connected_note_groups: [Personal, Work]\n entities: [Carlos, Ana]\n ---
│   │   ├── books.md
│   │   └── places.md
├── Personal/
│   └── 2026-03-11-walk-in-park.md
├── Ideas/
│   └── 2026-03-11-app-concept.md
└── Work/
    └── 2026-03-11-meeting-carlos.md
```

### Note frontmatter

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

## 2. Message Flow

```
incoming message
    │
    ├─ COMMAND? ──► execute registry operation ──► inform user ──► done
    │
    └─ NOTE? ──► Step 1: detect note group (ask|guess)
                    │
                    ├─► Step 2: detect entities (ask|guess)
                    │
                    ├─► Step 3: final review (ALWAYS ask)
                    │       "Note group: Personal
                    │        Entities: Carlos (friends)
                    │        File: Personal/2026-03-11-walk-in-park.md
                    │        Approve, modify, or cancel?"
                    │
                    └─► Step 4: save note + git commit/push

```

**Commands** (registry operations):
- `add note group X` / `add note groups X, Y, Z`
- `add entity group X connected to Y, Z`
- `add entities A, B, C to entity group X`
- Batch operations supported

**Flow config** (hardcoded, tunable per step):
```python
FLOW_CONFIG = {
    "detect_note_group": "guess",  # "ask" | "guess"
    "detect_entities": "ask",      # "ask" | "guess"
}
# Final review is always "ask" (mandatory, not configurable)
```

### Note path: step-by-step agent execution

This is a single LangChain 1.0 agent running its standard tool-calling loop. Each step is an LLM reasoning turn → tool call → result → next reasoning turn. The system prompt enforces the order.

**Step 1: Detect Note Group**
- Agent calls `list_note_groups()` → gets `["Personal", "Ideas", "Work"]`
- LLM analyzes note text against available groups
- If `guess`: picks best match, stores in message history, proceeds
- If `ask`: calls `ask_user("Detected note group: Personal. Confirm or change?")` → `interrupt()` fires → agent pauses → Telegram sends question → user replies → `Command(resume="Personal")` feeds back → agent continues

**Step 2: Detect Entities**
- Agent calls `get_entities_for_note_group("Personal")` → returns `{friends: [Carlos, Ana], places: [Central Park]}`
- LLM scans note text for matches against these entities
- If `guess`: assigns detected entities, proceeds
- If `ask`: calls `ask_user("Found entities: Carlos (friends). Confirm, add, or remove?")` → interrupt/resume cycle

**Step 3: Final Review (always)**
- Agent MUST call `ask_user` with full summary (note group, entities, entity groups, file path)
- System prompt enforces: "NEVER call save_note without calling ask_user for final review first"
- User can: approve → proceed to save | modify → agent updates, re-presents | cancel → no save

**Step 4: Save**
- Agent calls `save_note(note_group="Personal", content="...", entities=["Carlos"], entity_groups=["friends"], slug="walk-in-park")`
- Tool writes frontmatter + content to `Personal/2026-03-11-walk-in-park.md`
- Tool calls git sync (commit + push)
- Agent returns confirmation message to user

## 3. Agent & Tools

### LangChain 1.0 agent setup

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    ChatOpenAI(model="gpt-4o", temperature=0),
    tools=[...],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)
```

### Tools

**Registry tools:**
- `list_note_groups()` → reads `_meta/note_groups/`, returns list
- `add_note_group(name)` → creates `_meta/note_groups/{name}.md` + vault folder
- `list_entity_groups()` → reads `_meta/entity_groups/`
- `add_entity_group(name, connected_note_groups)` → creates `_meta/entity_groups/{name}.md`
- `add_entities_to_group(group_name, entities[])` → updates entity group file
- `get_entities_for_note_group(note_group)` → finds connected entity groups, returns their entities

**Note tools:**
- `save_note(note_group, content, entities[], entity_groups[], slug)` → writes frontmatter + content to `{NoteGroup}/{date}-{slug}.md`, git sync
- `search_vault(query)` → search all markdown files
- `read_note(path)` → read a note

**Interaction tool:**
- `ask_user(question)` → calls `interrupt({"question": question})`, returns user's reply

### System prompt (injected with FLOW_CONFIG)

The system prompt instructs the agent to:
1. Classify message as COMMAND or NOTE
2. If COMMAND: execute, inform
3. If NOTE: detect note group (per config mode) → detect entities (per config mode) → always present final review via `ask_user` → save on approval

## 4. Multi-turn via LangGraph interrupt

### How it works

The `ask_user` tool calls `interrupt()` from `langgraph.types`. The agent pauses, the handler sends the question to Telegram, and when the user replies, the handler resumes via `Command(resume=user_reply)`.

### Handler flow

```python
# New message, no active session
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": transcript}]},
    config={"configurable": {"thread_id": str(user_id)}}
)

# If interrupted → send question to user, wait for reply
# On reply → resume
result = await agent.ainvoke(
    Command(resume=user_reply),
    config={"configurable": {"thread_id": str(user_id)}}
)
```

Thread ID = Telegram user_id. Timeout: 10 min, then session discarded.

## 5. Infrastructure (adapted from zenith)

### Dockerfile
- Multi-stage: `uv` builder + Python 3.11-slim runtime
- Runtime deps: `git`, `curl` (no Node.js needed)
- Non-root user, healthcheck via curl

### docker-compose.yml (dev)
- Single `bot` service
- Vault repo mounted as volume
- Hot-reload via source mount
- Environment variables from `.env`

### docker-compose.prod.yml
- `restart: always`
- No source mount
- `ENVIRONMENT=production`

### Deploy scripts (from zenith, adapted)
- `deploy/digital-ocean-setup.sh` — Docker, UFW (SSH only), fail2ban
- `deploy/setup-new-droplet.sh` — SSH keys, deploy key, clone app repo + clone vault repo, copy .env, build, start
- `deploy/deploy-prod.sh` — git pull, docker build, restart

### CI/CD GitHub Actions
- CI: test + Docker build on push/PR
- CD: SSH deploy to DO on main push

### Makefile
- `make dev`, `make prod`, `make deploy`, `make logs`, `make test`

## 6. Files to Create/Modify

### New files
- `bot/tools/registry.py` — registry tools (list/add note groups, entity groups, entities)
- `bot/tools/notes.py` — note tools (save_note, search, read)
- `bot/tools/interaction.py` — ask_user tool (interrupt-based)
- `bot/session.py` — session/handler logic for multi-turn (interrupt/resume)
- `Dockerfile`
- `infrastructure/docker-compose.yml`
- `infrastructure/docker-compose.prod.yml`
- `deploy/digital-ocean-setup.sh`
- `deploy/setup-new-droplet.sh`
- `deploy/deploy-prod.sh`
- `.github/workflows/ci.yml`
- `.github/workflows/cd.yml`
- `Makefile`

### Modified files
- `bot/brain.py` — replace with LangChain 1.0 `create_agent` + new tools + checkpointer
- `bot/handlers.py` — add interrupt/resume logic, route continuations vs new messages
- `bot/config.py` — add `FLOW_CONFIG`, remove MCP-related config
- `requirements.txt` — add `langgraph`, remove `mcp`, `langchain-mcp-adapters`
- `.env.example` — add `FLOW_CONFIG` vars, vault repo config

### Removed/deprecated
- `bot/vault/operations.py` — replaced by `bot/tools/` modules
- MCP dependency removed entirely

## 7. Git Sync After Note Save

Every successful `save_note()` call triggers:
1. `git add {note_path}` — stage the new note
2. `git add _meta/` — stage any registry changes from commands
3. `git commit -m "note: {slug} [{note_group}]"` — commit with descriptive message
4. `git push` — push to GitHub (vault's single source of truth)

This reuses `bot/vault/git_sync.py` (already exists). The `save_note` tool calls `git_sync.sync_write()` at the end. Commands that modify `_meta/` also trigger a commit+push via the same mechanism.

Pull before write is also maintained: `git_sync.pull()` is called at the start of every incoming message (already in `handlers.py`).

## 8. Setup Guide

### Local Development

**Prerequisites:** Python 3.11+, Docker, git, a Telegram bot token (from @BotFather), an OpenAI API key.

1. Clone the repo: `git clone <repo-url> && cd talkvault`
2. Copy env: `cp .env.example .env` → fill in `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`
3. Create a vault repo (or use existing): `mkdir vault && cd vault && git init` → set `VAULT_REPO_PATH` in `.env`
4. Seed the vault registry:
   ```
   mkdir -p vault/_meta/note_groups vault/_meta/entity_groups
   ```
5. Start with Docker: `make dev` (or without Docker: `pip install -r requirements.txt && python -m bot.main`)
6. Send a message to your Telegram bot to test

### DigitalOcean Production

**Prerequisites:** A DigitalOcean droplet (Ubuntu 22.04+, 1GB RAM minimum), a GitHub repo for the app, a GitHub repo for the vault.

1. **Create droplet** on DigitalOcean (Ubuntu 22.04, Basic, $6/mo is sufficient)
2. **Run setup script** from your local machine:
   ```
   ./deploy/setup-new-droplet.sh <DROPLET_IP>
   ```
   This script handles: SSH key setup, system packages, Docker, firewall, fail2ban, GitHub deploy keys, cloning both repos (app + vault), copying `.env`, building and starting the bot.
3. **Configure vault repo access**: The setup script creates a deploy key for the vault repo. Add it to your vault repo's GitHub settings (Settings → Deploy Keys → Allow write access).
4. **Set GitHub Actions secrets** (for CI/CD auto-deploy):
   - `DO_HOST`: droplet IP
   - `DO_USERNAME`: root
   - `DO_SSH_KEY`: your SSH private key
   - `OPENAI_API_KEY`: for CI tests
5. **Verify**: `ssh docean 'cd /opt/talkvault && docker compose logs -f'` — send a Telegram message, confirm it works.

### Manual updates (if not using CI/CD)

SSH into the droplet and run:
```
cd /opt/talkvault && ./deploy/deploy-prod.sh
```

## 9. Verification

1. **Unit tests**: Test each tool in isolation (create note group, add entity, save note with frontmatter)
2. **Flow test**: Send a note message, verify note group detection → entity detection → final review → save with correct frontmatter
3. **Command test**: Send "add entity group hobbies connected to Personal", verify `_meta/entity_groups/hobbies.md` created
4. **Multi-turn test**: Configure `detect_entities: "ask"`, send a note, verify bot asks for entity confirmation, reply, verify note saved
5. **Docker test**: `make dev`, send Telegram message, verify end-to-end
6. **Git sync test**: Verify note creation triggers git commit+push
