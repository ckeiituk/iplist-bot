import httpx
import logging
from config import GEMINI_API_KEYS, GEMINI_MODEL
from services.search import search_web, fetch_page_content

logger = logging.getLogger(__name__)

current_key_index = 0

def get_next_gemini_key():
    """Rotate to the next available API key."""
    global current_key_index
    if not GEMINI_API_KEYS or GEMINI_API_KEYS == [""]:
        raise ValueError("No GEMINI_API_KEY provided")
    
    key = GEMINI_API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(GEMINI_API_KEYS)
    return key

async def call_gemini_api(prompt: str, max_tokens: int = 50) -> str:
    """Call Gemini API with automatic key rotation on 429/403 errors."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.1
        }
    }

    attempts = len(GEMINI_API_KEYS)
    last_error = None

    for _ in range(attempts):
        try:
            api_key = get_next_gemini_key()
        except ValueError:
             raise ValueError("GEMINI_API_KEY not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{url}?key={api_key}", 
                    headers={"Content-Type": "application/json"}, 
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result and result["candidates"]:
                         return result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    else:
                         raise ValueError("No candidates returned from Gemini")

                if response.status_code in [429, 403]:
                    logger.warning(f"Gemini API key {api_key[:5]}... failed with {response.status_code}. Rotating key.")
                    last_error = response
                    continue
                
                response.raise_for_status()
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP Error with key {api_key[:5]}...: {e}")
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
    
    raise last_error if last_error else ValueError("All Gemini API keys failed")


async def classify_domain(domain: str, categories: list[str]) -> str:
    """Use Gemini API to classify domain into a category."""
    
    # Perform web search to get context
    context_source = "web search"
    search_results = ""
    
    try:
        search_results = search_web(domain, num_results=3)
    except Exception as e:
        logger.warning(f"Web search failed for {domain}: {e}")
        
    if not search_results or "No search results found" in search_results:
        logger.info(f"Search yielded no results for {domain}. Attempting direct page fetch.")
        context_source = "page content"
        try:
            search_results = await fetch_page_content(domain)
            if not search_results:
                search_results = "No content available."
        except Exception as e:
             logger.warning(f"Page fetch failed for {domain}: {e}")
             search_results = "Content unavailable."

    logger.info(f"Classifying domain: {domain}")
    logger.info(f"Context ({context_source}) for {domain}:\n{search_results[:500]}...") # Log 500 chars

    categories_str = ", ".join(categories)
    prompt = (
        f"Context from {context_source} for {domain}:\n"
        f"{search_results}\n\n"
        f"Based on this context and the domain name, which of these categories fits best: [{categories_str}]? "
        f"Answer ONLY with the name of the category from the list, without explanation."
    )
    
    logger.info(f"Gemini Prompt:\n{prompt}")

    try:
        category_text = await call_gemini_api(prompt, max_tokens=50)
        logger.info(f"Gemini Raw Response: {category_text}")
        category = category_text.lower()
    except Exception as e:
        logger.error(f"Classify domain failed: {e}")
        raise

    if category not in [c.lower() for c in categories]:
        raise ValueError(f"AI вернул неизвестную категорию: {category}")
    
    for cat in categories:
        if cat.lower() == category:
            return cat
    
    return category


async def resolve_domain_from_keyword(keyword: str) -> str:
    """Use Gemini to resolve domain from keyword."""
    prompt = (
        f"Какой основной домен у сервиса '{keyword}'? "
        f"Верни ТОЛЬКО домен без http://, www. и пояснений. "
        f"Если не уверен или это не известный сервис, верни 'UNKNOWN'."
    )
    
    try:
        domain = await call_gemini_api(prompt, max_tokens=30)
        domain = domain.lower()
    except Exception as e:
        logger.error(f"Resolve domain failed: {e}")
        raise ValueError(f"Ошибка AI: {e}")
    
    domain = domain.replace("http://", "").replace("https://", "").replace("www.", "").rstrip("/")
    
    if "unknown" in domain or len(domain) > 100 or " " in domain:
        raise ValueError(f"Не удалось определить домен для '{keyword}'")
    
    return domain
