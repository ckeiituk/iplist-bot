"""
Resolve domain from keyword using Gemini AI.
"""

from bot.core.logging import get_logger
from bot.core.exceptions import DomainResolutionError
from .client import GeminiClient

logger = get_logger(__name__)


async def resolve_domain_from_keyword(client: GeminiClient, keyword: str) -> str:
    """
    Use Gemini to resolve domain from a keyword/service name.
    
    Args:
        client: Gemini API client
        keyword: Service name or keyword
        
    Returns:
        Resolved domain name
        
    Raises:
        DomainResolutionError: If domain cannot be resolved
    """
    prompt = (
        f"Какой основной домен у сервиса '{keyword}'? "
        f"Верни ТОЛЬКО домен без http://, www. и пояснений. "
        f"Если не уверен или это не известный сервис, верни 'UNKNOWN'."
    )
    
    try:
        domain = await client.generate(prompt, max_tokens=30)
        domain = domain.lower()
    except Exception as e:
        logger.error(f"Resolve domain failed: {e}")
        raise DomainResolutionError(f"Ошибка AI: {e}")
    
    # Clean up domain
    domain = (
        domain.replace("http://", "")
        .replace("https://", "")
        .replace("www.", "")
        .rstrip("/")
    )
    
    # Validate response
    if "unknown" in domain or len(domain) > 100 or " " in domain:
        raise DomainResolutionError(f"Не удалось определить домен для '{keyword}'")
    
    return domain
