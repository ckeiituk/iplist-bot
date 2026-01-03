# Services module - external API integrations
from .dns import DNSResolver
from .search import WebSearcher

__all__ = ["DNSResolver", "WebSearcher"]
