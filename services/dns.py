"""
DNS resolution service.
"""

import dns.resolver
from bot.core.logging import get_logger
from bot.core.exceptions import DNSResolutionError

logger = get_logger(__name__)


class DNSResolver:
    """DNS resolver for domain IP lookups."""
    
    def __init__(self, timeout: int = 5, lifetime: int = 10):
        self._resolver = dns.resolver.Resolver()
        self._resolver.timeout = timeout
        self._resolver.lifetime = lifetime
    
    def resolve(self, domain: str) -> tuple[list[str], list[str]]:
        """
        Resolve A and AAAA records for domain.
        
        Args:
            domain: Domain name to resolve
            
        Returns:
            Tuple of (ipv4_list, ipv6_list)
        """
        ip4 = self._resolve_a(domain)
        ip6 = self._resolve_aaaa(domain)
        return ip4, ip6
    
    def _resolve_a(self, domain: str) -> list[str]:
        """Resolve A (IPv4) records."""
        try:
            answers = self._resolver.resolve(domain, "A")
            return [str(rdata) for rdata in answers]
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            logger.warning(f"No A records found for {domain}")
            return []
    
    def _resolve_aaaa(self, domain: str) -> list[str]:
        """Resolve AAAA (IPv6) records."""
        try:
            answers = self._resolver.resolve(domain, "AAAA")
            return [str(rdata) for rdata in answers]
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            logger.warning(f"No AAAA records found for {domain}")
            return []


# Default resolver instance
default_resolver = DNSResolver()


def resolve_dns(domain: str) -> tuple[list[str], list[str]]:
    """Convenience function using default resolver."""
    return default_resolver.resolve(domain)
