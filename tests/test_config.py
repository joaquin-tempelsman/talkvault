# tests/test_config.py
import os
import importlib
from unittest.mock import patch


def test_config_loads_required_vars():
    with patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "tok",
        "OPENAI_API_KEY": "sk-test",
    }):
        import bot.config as cfg
        importlib.reload(cfg)
        assert cfg.TELEGRAM_BOT_TOKEN == "tok"
        assert cfg.OPENAI_API_KEY == "sk-test"


def test_flow_config_defaults():
    with patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "tok",
        "OPENAI_API_KEY": "sk-test",
    }, clear=False):
        import bot.config as cfg
        importlib.reload(cfg)
        assert cfg.FLOW_CONFIG["detect_note_group"] in ("ask", "guess")
        assert cfg.FLOW_CONFIG["detect_entities"] in ("ask", "guess")


def test_flow_config_from_env():
    with patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "tok",
        "OPENAI_API_KEY": "sk-test",
        "FLOW_DETECT_NOTE_GROUP": "ask",
        "FLOW_DETECT_ENTITIES": "guess",
    }):
        import bot.config as cfg
        importlib.reload(cfg)
        assert cfg.FLOW_CONFIG["detect_note_group"] == "ask"
        assert cfg.FLOW_CONFIG["detect_entities"] == "guess"
