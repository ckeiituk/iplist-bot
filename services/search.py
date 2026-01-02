import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

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
