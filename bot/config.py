# bot/config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
VAULT_REPO_PATH: str = os.getenv("VAULT_REPO_PATH", "/opt/talkvault/vault")
VAULT_GITHUB_REPO: str = os.getenv("VAULT_GITHUB_REPO", "")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
