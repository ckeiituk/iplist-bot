"""
Data schemas for GitHub repository content.
"""

from dataclasses import dataclass, field, asdict
import json


@dataclass
class ExternalConfig:
    """External resources configuration."""
    
    domains: list[str] = field(default_factory=list)
    ip4: list[str] = field(default_factory=list)
    ip6: list[str] = field(default_factory=list)
    cidr4: list[str] = field(default_factory=list)
    cidr6: list[str] = field(default_factory=list)


@dataclass
class SiteConfig:
    """Site configuration for iplist."""
    
    domains: list[str]
    dns: list[str]
    ip4: list[str]
    ip6: list[str]
    timeout: int = 3600
    cidr4: list[str] = field(default_factory=list)
    cidr6: list[str] = field(default_factory=list)
    external: ExternalConfig = field(default_factory=ExternalConfig)
    
    @classmethod
    def create(
        cls,
        domain: str,
        dns_servers: list[str],
        ip4: list[str],
        ip6: list[str],
    ) -> "SiteConfig":
        """Create a site config for a domain."""
        return cls(
            domains=[domain, f"www.{domain}"],
            dns=dns_servers,
            ip4=ip4,
            ip6=ip6,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self, indent: int = 4) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
