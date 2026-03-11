# tests/test_config.py
import os, pytest
from unittest.mock import patch


def test_config_loads_required_vars():
    with patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "tok",
        "OPENAI_API_KEY": "sk-test",
    }):
        import importlib
        import bot.config as cfg
        importlib.reload(cfg)
        assert cfg.TELEGRAM_BOT_TOKEN == "tok"
        assert cfg.OPENAI_API_KEY == "sk-test"
