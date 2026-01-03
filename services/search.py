"""
Web search and page content fetching services.
"""

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from bot.core.logging import get_logger

logger = get_logger(__name__)


class WebSearcher:
    """Web search and content fetching service."""
    
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout
    
    def search(self, query: str, num_results: int = 3) -> str:
        """
        Search the web for the query.
        
        Args:
            query: Search query
            num_results: Maximum number of results
            
        Returns:
            Formatted string with search results
        """
        try:
            # Quote the query for exact domain matches
            search_query = f'"{query}"'
            results = DDGS().text(search_query, max_results=num_results, backend="html")
            if not results:
                return "No search results found."
            
            formatted_results = []
            for result in results:
                title = result.get("title", "No Title")
                snippet = result.get("body", "No Snippet")
                formatted_results.append(f"Title: {title}\nSnippet: {snippet}")
            
            return "\n\n".join(formatted_results)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Error performing search: {e}"
    
    async def fetch_page(self, domain: str, max_chars: int = 2000) -> str:
        """
        Fetch and extract text content from domain homepage.
        
        Args:
            domain: Domain name
            max_chars: Maximum characters to return
            
        Returns:
            Extracted text content
        """
        url = f"https://{domain}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text()
                
                # Break into lines and clean up
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = "\n".join(chunk for chunk in chunks if chunk)
                
                return text[:max_chars]
                
        except Exception as e:
            logger.warning(f"Failed to fetch content from {domain}: {e}")
            return ""


# Default searcher instance
default_searcher = WebSearcher()


def search_web(query: str, num_results: int = 3) -> str:
    """Convenience function using default searcher."""
    return default_searcher.search(query, num_results)


async def fetch_page_content(domain: str, max_chars: int = 2000) -> str:
    """Convenience function using default searcher."""
    return await default_searcher.fetch_page(domain, max_chars)
