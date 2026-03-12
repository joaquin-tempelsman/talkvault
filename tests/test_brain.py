# tests/test_brain.py
import os
import pytest
from unittest.mock import patch, MagicMock


def test_get_agent_creates_singleton(seeded_vault):
    """Agent is created once and reused."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "TELEGRAM_BOT_TOKEN": "test"}):
        # Reset singleton
        import bot.brain
        bot.brain._agent = None

        with patch("bot.brain.create_agent") as mock_create:
            mock_agent = MagicMock()
            mock_create.return_value = mock_agent

            agent1 = bot.brain.get_agent(seeded_vault)
            agent2 = bot.brain.get_agent(seeded_vault)

            assert agent1 is agent2
            mock_create.assert_called_once()

        # Clean up singleton for other tests
        bot.brain._agent = None


def test_system_prompt_includes_flow_config():
    """System prompt has the FLOW_CONFIG values injected."""
    from bot.brain import SYSTEM_PROMPT
    # Default config: detect_note_group=guess, detect_entities=ask
    assert "guess" in SYSTEM_PROMPT or "ask" in SYSTEM_PROMPT
    assert "NEVER call save_note without" in SYSTEM_PROMPT
