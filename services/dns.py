import dns.resolver
import logging
from config import DNS_SERVERS

logger = logging.getLogger(__name__)

def resolve_dns(domain: str) -> tuple[list[str], list[str]]:
    """Resolve A and AAAA records for domain."""
    ip4 = []
    ip6 = []
    
    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 10
    
    # Optional: configure specific nameservers if needed
    # resolver.nameservers = ['8.8.8.8'] # The bot uses system resolver or custom logic? 
    # The original code imported DNS_SERVERS but didn't seem to apply them to the resolver object explicitly 
    # in the snippet I saw. It used them for JSON output.
    
    # Resolve A records (IPv4)
    try:
        answers = resolver.resolve(domain, 'A')
        ip4 = [str(rdata) for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        logger.warning(f"No A records found for {domain}")
    
    # Resolve AAAA records (IPv6)
    try:
        answers = resolver.resolve(domain, 'AAAA')
        ip6 = [str(rdata) for rdata in answers]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        logger.warning(f"No AAAA records found for {domain}")
    
    return ip4, ip6
