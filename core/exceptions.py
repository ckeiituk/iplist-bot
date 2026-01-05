"""
Custom application exceptions.
"""


class BotError(Exception):
    """Base exception for bot errors."""
    pass


class DomainResolutionError(BotError):
    """Failed to resolve domain from keyword."""
    pass


class CategoryNotFoundError(BotError):
    """Category not found in GitHub repository."""
    pass


class DNSResolutionError(BotError):
    """Failed to resolve DNS for domain."""
    pass


class APIError(BotError):
    """External API call failed."""
    pass


class GeminiAPIError(APIError):
    """Gemini API call failed."""
    pass


class GitHubAPIError(APIError):
    """GitHub API call failed."""
    pass


class CollectorAPIError(APIError):
    """Collector API call failed."""
    pass
