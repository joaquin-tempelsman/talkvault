# bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
VAULT_REPO_PATH: str = os.getenv("VAULT_REPO_PATH", "/opt/talkvault/vault")
VAULT_GITHUB_REPO: str = os.getenv("VAULT_GITHUB_REPO", "")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Flow config: per-step "ask" or "guess"
FLOW_CONFIG: dict = {
    "detect_note_group": os.getenv("FLOW_DETECT_NOTE_GROUP", "guess"),
    "detect_entities": os.getenv("FLOW_DETECT_ENTITIES", "ask"),
}

# Session timeout in seconds (10 minutes)
SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", "600"))
