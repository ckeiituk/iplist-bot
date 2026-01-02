import logging
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

async def fetch_page_content(domain: str, max_chars: int = 2000) -> str:
    """
    Fetch the homepage of the domain and extract text content.
    """
    url = f"https://{domain}"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            text = soup.get_text()
            
            # Break into lines and remove leading/trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text[:max_chars]
            
    except Exception as e:
        logger.warning(f"Failed to fetch content from {domain}: {e}")
        return ""


def search_web(query: str, num_results: int = 3) -> str:
    """
    Search the web for the query and return a concatenated string of results.
    Each result includes the title and snippet.
    """
    try:
        results = DDGS().text(query, max_results=num_results)
        if not results:
            return "No search results found."
        
        formatted_results = []
        for result in results:
            title = result.get('title', 'No Title')
            snippet = result.get('body', 'No Snippet')
            formatted_results.append(f"Title: {title}\nSnippet: {snippet}")
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Error performing search: {e}"
