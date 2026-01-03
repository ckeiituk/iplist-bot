"""
Pytest configuration and shared fixtures.
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Add bot package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Environment Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("TG_TOKEN", "test_token_123")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token")
    monkeypatch.setenv("GEMINI_API_KEY", "key1,key2,key3")
    monkeypatch.setenv("LOG_CHANNEL_ID", "-100123456789:42")
    monkeypatch.setenv("WEBHOOK_SECRET", "test_secret")


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_bot():
    """Create a mock Telegram Bot."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update."""
    update = MagicMock()
    update.effective_user.id = 123456
    update.effective_user.username = "testuser"
    update.effective_user.full_name = "Test User"
    update.effective_chat.id = -100987654321
    update.effective_message.message_thread_id = None
    update.effective_message.is_topic_message = False
    update.message.text = "example.com"
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context(mock_bot):
    """Create a mock Telegram Context."""
    context = MagicMock()
    context.bot = mock_bot
    context.args = []
    return context


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        yield client_instance


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest.fixture
def gemini_client():
    """Create a GeminiClient with test keys."""
    from bot.services.ai.client import GeminiClient
    return GeminiClient(["key1", "key2", "key3"], "test-model")


@pytest.fixture
def github_client():
    """Create a GitHubClient with test config."""
    from bot.services.github.client import GitHubClient
    return GitHubClient("ghp_test", "test/repo", "main")


@pytest.fixture
def web_searcher():
    """Create a WebSearcher instance."""
    from bot.services.search import WebSearcher
    return WebSearcher()


@pytest.fixture
def dns_resolver():
    """Create a DNSResolver instance."""
    from bot.services.dns import DNSResolver
    return DNSResolver()
