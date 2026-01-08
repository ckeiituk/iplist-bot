"""
DNS resolution service.
"""

from dataclasses import dataclass
from typing import Literal

import dns.resolver
from bot.core.config import settings
from bot.core.logging import get_logger

logger = get_logger(__name__)

DNSResolutionIssue = Literal[
    "nxdomain",
    "no_answer",
    "no_nameservers",
    "timeout",
    "error",
]


@dataclass(frozen=True)
class DNSResolutionResult:
    """Result of a DNS lookup with optional failure reason."""

    ip4: list[str]
    ip6: list[str]
    issue: DNSResolutionIssue | None = None


def _normalize_nameservers(nameservers: list[str]) -> list[str]:
    normalized: list[str] = []
    for entry in nameservers:
        value = entry.strip()
        if not value:
            continue
        if value.startswith("[") and "]" in value:
            value = value[1:value.index("]")]
        elif value.count(":") == 1 and "." in value:
            value = value.split(":", 1)[0]
        normalized.append(value)
    return normalized


class DNSResolver:
    """DNS resolver for domain IP lookups."""

    def __init__(
        self,
        timeout: int = 5,
        lifetime: int = 10,
        nameservers: list[str] | None = None,
    ):
        if nameservers:
            normalized = _normalize_nameservers(nameservers)
            if normalized:
                self._resolver = dns.resolver.Resolver(configure=False)
                self._resolver.nameservers = normalized
            else:
                self._resolver = dns.resolver.Resolver()
        else:
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
        result = self.resolve_with_reason(domain)
        return result.ip4, result.ip6

    def resolve_with_reason(self, domain: str) -> DNSResolutionResult:
        """Resolve A and AAAA records for domain with failure details."""
        ip4, issue4 = self._resolve_record(domain, "A")
        ip6, issue6 = self._resolve_record(domain, "AAAA")

        issue = None
        if not ip4 and not ip6:
            issue = self._pick_issue(issue4, issue6)

        return DNSResolutionResult(ip4=ip4, ip6=ip6, issue=issue)

    @staticmethod
    def _pick_issue(
        issue4: DNSResolutionIssue | None,
        issue6: DNSResolutionIssue | None,
    ) -> DNSResolutionIssue | None:
        issues = {issue4, issue6}
        for candidate in ("nxdomain", "no_nameservers", "timeout", "no_answer", "error"):
            if candidate in issues:
                return candidate
        return issue4 or issue6

    def _resolve_record(
        self,
        domain: str,
        record_type: str,
    ) -> tuple[list[str], DNSResolutionIssue | None]:
        """Resolve DNS records with error classification."""
        try:
            answers = self._resolver.resolve(domain, record_type)
            return [str(rdata) for rdata in answers], None
        except dns.resolver.NXDOMAIN:
            logger.warning("NXDOMAIN for %s", domain)
            return [], "nxdomain"
        except dns.resolver.NoAnswer:
            logger.warning("No %s records found for %s", record_type, domain)
            return [], "no_answer"
        except dns.resolver.NoNameservers:
            logger.warning("No nameservers available for %s", domain)
            return [], "no_nameservers"
        except dns.exception.Timeout:
            logger.warning("DNS timeout for %s", domain)
            return [], "timeout"
        except dns.exception.DNSException as exc:
            logger.warning("DNS error for %s: %s", domain, exc)
            return [], "error"


_fallback_nameservers = _normalize_nameservers(settings.dns_servers)

# Default resolver instance
default_resolver = DNSResolver()
fallback_resolver = (
    DNSResolver(nameservers=_fallback_nameservers) if _fallback_nameservers else None
)


def resolve_dns(domain: str) -> tuple[list[str], list[str]]:
    """Convenience function using default resolver."""
    return default_resolver.resolve(domain)


def resolve_dns_with_reason(domain: str) -> DNSResolutionResult:
    """Convenience function using default resolver with error detail."""
    primary = default_resolver.resolve_with_reason(domain)
    if primary.ip4 or primary.ip6 or fallback_resolver is None:
        return primary

    fallback = fallback_resolver.resolve_with_reason(domain)
    if fallback.ip4 or fallback.ip6:
        return fallback

    issue = fallback.issue or primary.issue
    return DNSResolutionResult(ip4=[], ip6=[], issue=issue)
