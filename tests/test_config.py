"""
Tests for core.config module.
"""

import os
import pytest


class TestSettings:
    """Tests for Settings class."""
    
    def test_required_tokens_loaded(self):
        """Test that required tokens are loaded from environment."""
        # Import after env is set by fixture
        from bot.core.config import Settings
        
        settings = Settings()
        assert settings.tg_token == "test_token_123"
        assert settings.github_token == "ghp_test_token"
    
    def test_gemini_api_keys_parsed(self):
        """Test that comma-separated API keys are parsed correctly."""
        from bot.core.config import Settings
        
        settings = Settings()
        keys = settings.gemini_api_keys
        
        assert len(keys) == 3
        assert keys == ["key1", "key2", "key3"]
    
    def test_log_channel_with_topic_parsed(self):
        """Test that LOG_CHANNEL_ID:TOPIC_ID format is parsed."""
        from bot.core.config import Settings
        
        settings = Settings()
        
        assert settings.channel_id == -100123456789
        assert settings.topic_id == 42
    
    def test_log_channel_without_topic(self, monkeypatch):
        """Test LOG_CHANNEL_ID without topic."""
        monkeypatch.setenv("LOG_CHANNEL_ID", "-100555555555")
        
        from bot.core.config import Settings
        settings = Settings()
        
        assert settings.channel_id == -100555555555
        assert settings.topic_id is None

    def test_lk_admin_channel_with_topic(self, monkeypatch):
        """Test LK_ADMIN_CHANNEL_ID parsing."""
        monkeypatch.setenv("LK_ADMIN_CHANNEL_ID", "-100777777777:99")

        from bot.core.config import Settings
        settings = Settings()

        assert settings.lk_admin_channel == -100777777777
        assert settings.lk_admin_topic == 99

    def test_admin_user_ids_parsed(self, monkeypatch):
        """Test ADMIN_USER_IDS parsing."""
        monkeypatch.setenv("ADMIN_USER_IDS", "123, 456 789")

        from bot.core.config import Settings
        settings = Settings()

        assert settings.admin_ids == {123, 456, 789}
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        from bot.core.config import Settings
        
        settings = Settings()
        
        assert settings.github_repo == "ckeiituk/iplist"
        assert settings.github_branch == "master"
        assert settings.gemini_model == "gemma-3-27b-it"
        assert len(settings.dns_servers) == 4
    
    @pytest.mark.skip(reason="Settings reads from .env file directly, not affected by monkeypatch")
    def test_missing_required_token_raises(self, monkeypatch):
        """Test that missing required token raises ValidationError."""
        pass
    
    def test_empty_gemini_key_returns_fallback(self, monkeypatch):
        """Test empty GEMINI_API_KEY returns fallback."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        
        from bot.core.config import Settings
        settings = Settings()
        
        assert settings.gemini_api_keys == [""]
