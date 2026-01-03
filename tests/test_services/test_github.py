"""
Tests for GitHub service.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


class TestSiteConfig:
    """Tests for SiteConfig dataclass."""
    
    def test_create_basic(self):
        """Test basic SiteConfig creation."""
        from bot.services.github.schemas import SiteConfig
        
        config = SiteConfig.create(
            domain="example.com",
            dns_servers=["8.8.8.8:53"],
            ip4=["1.2.3.4"],
            ip6=["2001:db8::1"],
        )
        
        assert config.domains == ["example.com", "www.example.com"]
        assert config.dns == ["8.8.8.8:53"]
        assert config.ip4 == ["1.2.3.4"]
        assert config.ip6 == ["2001:db8::1"]
        assert config.timeout == 3600
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        from bot.services.github.schemas import SiteConfig
        
        config = SiteConfig.create("test.com", ["8.8.8.8:53"], ["1.1.1.1"], [])
        result = config.to_dict()
        
        assert isinstance(result, dict)
        assert result["domains"] == ["test.com", "www.test.com"]
        assert "external" in result
    
    def test_to_json(self):
        """Test JSON serialization."""
        from bot.services.github.schemas import SiteConfig
        
        config = SiteConfig.create("test.com", ["8.8.8.8:53"], ["1.1.1.1"], [])
        json_str = config.to_json()
        
        assert isinstance(json_str, str)
        assert '"domains"' in json_str
        assert "test.com" in json_str


class TestGitHubClient:
    """Tests for GitHubClient class."""
    
    def test_init(self, github_client):
        """Test client initialization."""
        assert github_client._token == "ghp_test"
        assert github_client._repo == "test/repo"
        assert github_client._branch == "main"
    
    @pytest.mark.asyncio
    async def test_get_categories_success(self, github_client):
        """Test successful categories fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "games", "type": "dir"},
            {"name": "social", "type": "dir"},
            {"name": "README.md", "type": "file"},
        ]
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            categories = await github_client.get_categories()
            
            assert categories == ["games", "social"]
            assert "README.md" not in categories
    
    @pytest.mark.asyncio
    async def test_get_categories_error_raises(self, github_client):
        """Test that API error raises GitHubAPIError."""
        from bot.core.exceptions import GitHubAPIError
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Network error")
            )
            
            with pytest.raises(GitHubAPIError):
                await github_client.get_categories()
    
    @pytest.mark.asyncio
    async def test_create_file_new(self, github_client):
        """Test creating a new file."""
        from bot.services.github.schemas import SiteConfig
        
        # Mock GET returning 404 (file doesn't exist)
        mock_get = MagicMock()
        mock_get.status_code = 404
        
        # Mock PUT success
        mock_put = MagicMock()
        mock_put.status_code = 201
        mock_put.json.return_value = {
            "content": {"html_url": "https://github.com/test/file.json"},
            "commit": {"sha": "abc123"},
        }
        mock_put.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient") as mock_client:
            client_instance = mock_client.return_value.__aenter__.return_value
            client_instance.get = AsyncMock(return_value=mock_get)
            client_instance.put = AsyncMock(return_value=mock_put)
            
            config = SiteConfig.create("test.com", ["8.8.8.8:53"], ["1.2.3.4"], [])
            html_url, sha = await github_client.create_file("games", "test.com", config)
            
            assert html_url == "https://github.com/test/file.json"
            assert sha == "abc123"
    
    @pytest.mark.asyncio
    async def test_create_file_update_existing(self, github_client):
        """Test updating an existing file."""
        from bot.services.github.schemas import SiteConfig
        
        # Mock GET returning existing file
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"sha": "existing_sha"}
        
        # Mock PUT success
        mock_put = MagicMock()
        mock_put.status_code = 200
        mock_put.json.return_value = {
            "content": {"html_url": "https://github.com/test/file.json"},
            "commit": {"sha": "new_sha"},
        }
        mock_put.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient") as mock_client:
            client_instance = mock_client.return_value.__aenter__.return_value
            client_instance.get = AsyncMock(return_value=mock_get)
            client_instance.put = AsyncMock(return_value=mock_put)
            
            config = SiteConfig.create("test.com", ["8.8.8.8:53"], ["1.2.3.4"], [])
            await github_client.create_file("games", "test.com", config)
            
            # Verify PUT was called with sha for update
            put_call = client_instance.put.call_args
            assert "sha" in put_call.kwargs.get("json", {})
