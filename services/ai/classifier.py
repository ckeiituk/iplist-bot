"""
Domain classification using Gemini AI.
"""

from bot.core.logging import get_logger
from bot.core.exceptions import CategoryNotFoundError
from .client import GeminiClient
from bot.services.search import WebSearcher

logger = get_logger(__name__)


async def classify_domain(
    client: GeminiClient,
    searcher: WebSearcher,
    domain: str,
    categories: list[str],
) -> str:
    """
    Use Gemini API to classify domain into a category.
    
    Args:
        client: Gemini API client
        searcher: Web search service
        domain: Domain to classify
        categories: Available categories
        
    Returns:
        Matched category name
        
    Raises:
        CategoryNotFoundError: If AI returns unknown category
    """
    # Perform web search to get context
    context_source = "web search"
    search_results = ""
    
    try:
        search_results = searcher.search(domain, num_results=3)
    except Exception as e:
        logger.warning(f"Web search failed for {domain}: {e}")
    
    if not search_results or "No search results found" in search_results:
        pass  # Will trigger fallback
    else:
        # Heuristic: Check if domain name appears in search results
        domain_sld = domain.split(".")[0].lower()
        if domain_sld not in search_results.lower():
            logger.warning(
                f"Search results for {domain} seem irrelevant "
                f"(SLD '{domain_sld}' not found). Triggering fallback."
            )
            search_results = ""
    
    if not search_results or "No search results found" in search_results:
        logger.info(f"Search yielded no results for {domain}. Attempting direct page fetch.")
        context_source = "page content"
        try:
            search_results = await searcher.fetch_page(domain)
            if not search_results:
                search_results = "No content available."
        except Exception as e:
            logger.warning(f"Page fetch failed for {domain}: {e}")
            search_results = "Content unavailable."
    
    logger.info(f"Classifying domain: {domain}")
    logger.info(f"Context ({context_source}) for {domain}:\n{search_results[:500]}...")
    
    categories_str = ", ".join(categories)
    prompt = (
        f"Context from {context_source} for {domain}:\n"
        f"{search_results}\n\n"
        f"Based on this context and the domain name, which of these categories fits best: [{categories_str}]? "
        f"Answer ONLY with the name of the category from the list, without explanation."
    )
    
    logger.info(f"Gemini Prompt:\n{prompt}")
    
    category_text = await client.generate(prompt, max_tokens=50)
    logger.info(f"Gemini Raw Response: {category_text}")
    category = category_text.lower()
    
    # Validate category
    categories_lower = [c.lower() for c in categories]
    if category not in categories_lower:
        raise CategoryNotFoundError(f"AI вернул неизвестную категорию: {category}")
    
    # Return original case category
    for cat in categories:
        if cat.lower() == category:
            return cat
    
    return category
