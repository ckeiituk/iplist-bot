"""
Tests for Gemini AI service.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


class TestGeminiClient:
    """Tests for GeminiClient class."""
    
    def test_init_with_keys(self, gemini_client):
        """Test client initialization with API keys."""
        assert len(gemini_client._api_keys) == 3
        assert gemini_client._model == "test-model"
        assert gemini_client._current_key_index == 0
    
    def test_key_rotation(self, gemini_client):
        """Test that keys rotate correctly."""
        key1 = gemini_client._get_next_key()
        key2 = gemini_client._get_next_key()
        key3 = gemini_client._get_next_key()
        key4 = gemini_client._get_next_key()  # Should wrap around
        
        assert key1 == "key1"
        assert key2 == "key2"
        assert key3 == "key3"
        assert key4 == "key1"  # Wrapped
    
    def test_get_key_with_no_keys_raises(self):
        """Test that empty keys list raises error."""
        from bot.services.ai.client import GeminiClient
        from bot.core.exceptions import GeminiAPIError
        
        client = GeminiClient([], "model")
        
        with pytest.raises(GeminiAPIError, match="No GEMINI_API_KEY"):
            client._get_next_key()
    
    @pytest.mark.asyncio
    async def test_generate_success(self, gemini_client):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Test response"}]
                }
            }]
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await gemini_client.generate("Test prompt")
            
            assert result == "Test response"
    
    @pytest.mark.asyncio
    async def test_generate_rotates_on_429(self, gemini_client):
        """Test that client rotates keys on 429 error."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Success"}]}}]
        }
        
        call_count = 0
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_429
            return mock_success
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            result = await gemini_client.generate("Test")
            
            assert result == "Success"
            assert call_count == 2  # First failed, second succeeded
    
    @pytest.mark.asyncio
    async def test_generate_all_keys_fail_raises(self, gemini_client):
        """Test that error is raised when all keys fail."""
        from bot.core.exceptions import GeminiAPIError
        
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_429
            )
            
            with pytest.raises(GeminiAPIError):
                await gemini_client.generate("Test")


class TestClassifyDomain:
    """Tests for classify_domain function."""
    
    @pytest.mark.asyncio
    async def test_classify_returns_category(self, gemini_client, web_searcher):
        """Test that classify_domain returns a valid category."""
        from bot.services.ai.classifier import classify_domain
        
        categories = ["games", "social", "streaming"]
        
        with patch.object(web_searcher, 'search', return_value="store steampowered.com"):
            with patch.object(web_searcher, 'fetch_page', new_callable=AsyncMock, return_value=""):
                with patch.object(gemini_client, 'generate', new_callable=AsyncMock) as mock_gen:
                    mock_gen.return_value = "games"

                    result = await classify_domain(
                        gemini_client, web_searcher, "store.steampowered.com", categories
                    )

                    assert result == "games"
    
    @pytest.mark.asyncio
    async def test_classify_unknown_category_raises(self, gemini_client, web_searcher):
        """Test that unknown category raises error."""
        from bot.services.ai.classifier import classify_domain
        from bot.core.exceptions import CategoryNotFoundError
        
        categories = ["games", "social"]
        
        with patch.object(web_searcher, 'search', return_value="example.com content"):
            with patch.object(web_searcher, 'fetch_page', new_callable=AsyncMock, return_value=""):
                with patch.object(gemini_client, 'generate', new_callable=AsyncMock) as mock_gen:
                    mock_gen.return_value = "unknown_category"

                    with pytest.raises(CategoryNotFoundError):
                        await classify_domain(
                            gemini_client, web_searcher, "example.com", categories
                        )


class TestResolveDomainFromKeyword:
    """Tests for resolve_domain_from_keyword function."""
    
    @pytest.mark.asyncio
    async def test_resolve_returns_domain(self, gemini_client):
        """Test successful domain resolution."""
        from bot.services.ai.resolver import resolve_domain_from_keyword
        
        with patch.object(gemini_client, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "spotify.com"
            
            result = await resolve_domain_from_keyword(gemini_client, "spotify")
            
            assert result == "spotify.com"
    
    @pytest.mark.asyncio
    async def test_resolve_unknown_raises(self, gemini_client):
        """Test that UNKNOWN response raises error."""
        from bot.services.ai.resolver import resolve_domain_from_keyword
        from bot.core.exceptions import DomainResolutionError
        
        with patch.object(gemini_client, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "UNKNOWN"
            
            with pytest.raises(DomainResolutionError):
                await resolve_domain_from_keyword(gemini_client, "nonexistent")
    
    @pytest.mark.asyncio
    async def test_resolve_cleans_url(self, gemini_client):
        """Test that URLs are cleaned properly."""
        from bot.services.ai.resolver import resolve_domain_from_keyword
        
        with patch.object(gemini_client, 'generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "https://www.example.com/"
            
            result = await resolve_domain_from_keyword(gemini_client, "example")
            
            assert result == "example.com"
