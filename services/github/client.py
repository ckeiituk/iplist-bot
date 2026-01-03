"""
GitHub API client for iplist repository operations.
"""

import base64
import httpx
from bot.core.logging import get_logger
from bot.core.exceptions import GitHubAPIError
from .schemas import SiteConfig

logger = get_logger(__name__)


class GitHubClient:
    """Client for GitHub API operations on iplist repository."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str, repo: str, branch: str):
        self._token = token
        self._repo = repo
        self._branch = branch
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    
    async def get_categories(self) -> list[str]:
        """
        Get list of category folders from config/ directory.
        
        Returns:
            List of category names
            
        Raises:
            GitHubAPIError: If API call fails
        """
        url = f"{self.BASE_URL}/repos/{self._repo}/contents/config"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self._headers,
                    params={"ref": self._branch},
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise GitHubAPIError(f"Failed to get categories: {e}")
        
        contents = response.json()
        categories = [item["name"] for item in contents if item["type"] == "dir"]
        return categories
    
    async def create_file(
        self,
        category: str,
        domain: str,
        config: SiteConfig,
    ) -> tuple[str, str]:
        """
        Create or update a site config file in the repository.
        
        Args:
            category: Category folder name
            domain: Domain name (used as filename)
            config: Site configuration
            
        Returns:
            Tuple of (html_url, commit_sha)
            
        Raises:
            GitHubAPIError: If API call fails
        """
        file_path = f"config/{category}/{domain}.json"
        url = f"{self.BASE_URL}/repos/{self._repo}/contents/{file_path}"
        
        json_content = config.to_json()
        encoded_content = base64.b64encode(json_content.encode()).decode()
        
        data = {
            "message": f"feat({category}): add {domain}",
            "content": encoded_content,
            "branch": self._branch,
        }
        
        async with httpx.AsyncClient() as client:
            # Check if file exists to get sha for update
            try:
                get_response = await client.get(
                    url,
                    headers=self._headers,
                    params={"ref": self._branch},
                )
                if get_response.status_code == 200:
                    sha = get_response.json().get("sha")
                    data["sha"] = sha
                    data["message"] = f"fix({category}): update {domain}"
            except httpx.HTTPError:
                pass
            
            try:
                response = await client.put(url, headers=self._headers, json=data)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise GitHubAPIError(f"Failed to create file: {e}")
        
        result = response.json()
        html_url = result["content"]["html_url"]
        commit_sha = result["commit"]["sha"]
        return html_url, commit_sha
