"""
Tests for models module.
"""

import pytest
from unittest.mock import MagicMock


class TestPendingBuild:
    """Tests for PendingBuild dataclass."""
    
    def test_create_pending_build(self):
        """Test basic PendingBuild creation."""
        from bot.models.pending import PendingBuild
        
        mock_bot = MagicMock()
        build = PendingBuild(
            user_id=123,
            domain="example.com",
            chat_id=456,
            bot=mock_bot,
        )
        
        assert build.user_id == 123
        assert build.domain == "example.com"
        assert build.chat_id == 456
        assert build.bot is mock_bot
        assert build.message_thread_id is None
    
    def test_pending_build_with_thread(self):
        """Test PendingBuild with message_thread_id."""
        from bot.models.pending import PendingBuild
        
        mock_bot = MagicMock()
        build = PendingBuild(
            user_id=123,
            domain="example.com",
            chat_id=456,
            bot=mock_bot,
            message_thread_id=789,
        )
        
        assert build.message_thread_id == 789


class TestBuildsStore:
    """Tests for BuildsStore class."""
    
    def test_add_and_get(self):
        """Test adding and getting builds."""
        from bot.state.builds import BuildsStore
        from bot.models.pending import PendingBuild
        
        store = BuildsStore()
        mock_bot = MagicMock()
        build = PendingBuild(user_id=1, domain="test.com", chat_id=100, bot=mock_bot)
        
        store.add("sha123", build)
        
        assert "sha123" in store
        assert store.get("sha123") is build
    
    def test_pop_removes_build(self):
        """Test that pop removes the build."""
        from bot.state.builds import BuildsStore
        from bot.models.pending import PendingBuild
        
        store = BuildsStore()
        mock_bot = MagicMock()
        build = PendingBuild(user_id=1, domain="test.com", chat_id=100, bot=mock_bot)
        
        store.add("sha123", build)
        popped = store.pop("sha123")
        
        assert popped is build
        assert "sha123" not in store
    
    def test_pop_nonexistent_returns_none(self):
        """Test popping nonexistent key returns None."""
        from bot.state.builds import BuildsStore
        
        store = BuildsStore()
        assert store.pop("nonexistent") is None
    
    def test_get_all_shas(self):
        """Test getting all SHA keys."""
        from bot.state.builds import BuildsStore
        from bot.models.pending import PendingBuild
        
        store = BuildsStore()
        mock_bot = MagicMock()
        
        store.add("sha1", PendingBuild(user_id=1, domain="a.com", chat_id=1, bot=mock_bot))
        store.add("sha2", PendingBuild(user_id=2, domain="b.com", chat_id=2, bot=mock_bot))
        store.add("sha3", PendingBuild(user_id=3, domain="c.com", chat_id=3, bot=mock_bot))
        
        shas = store.get_all_shas()
        
        assert len(shas) == 3
        assert set(shas) == {"sha1", "sha2", "sha3"}
