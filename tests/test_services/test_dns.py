"""
Tests for DNS service.
"""

import pytest
from unittest.mock import patch, MagicMock
import dns.resolver


class TestDNSResolver:
    """Tests for DNSResolver class."""
    
    def test_resolve_returns_tuple(self, dns_resolver):
        """Test that resolve returns tuple of (ipv4, ipv6) lists."""
        with patch.object(dns_resolver._resolver, 'resolve') as mock_resolve:
            # Mock A record response
            mock_a = MagicMock()
            mock_a.__iter__ = lambda self: iter([MagicMock(__str__=lambda s: "1.2.3.4")])
            
            # Mock AAAA record response  
            mock_aaaa = MagicMock()
            mock_aaaa.__iter__ = lambda self: iter([MagicMock(__str__=lambda s: "2001:db8::1")])
            
            def side_effect(domain, record_type):
                if record_type == "A":
                    return mock_a
                return mock_aaaa
            
            mock_resolve.side_effect = side_effect
            
            ip4, ip6 = dns_resolver.resolve("example.com")
            
            assert isinstance(ip4, list)
            assert isinstance(ip6, list)
    
    def test_resolve_handles_nxdomain(self, dns_resolver):
        """Test handling of NXDOMAIN (domain doesn't exist)."""
        with patch.object(dns_resolver._resolver, 'resolve') as mock_resolve:
            mock_resolve.side_effect = dns.resolver.NXDOMAIN()
            
            ip4, ip6 = dns_resolver.resolve("nonexistent.invalid")
            
            assert ip4 == []
            assert ip6 == []
    
    def test_resolve_handles_no_answer(self, dns_resolver):
        """Test handling when domain exists but has no records."""
        with patch.object(dns_resolver._resolver, 'resolve') as mock_resolve:
            mock_resolve.side_effect = dns.resolver.NoAnswer()
            
            ip4, ip6 = dns_resolver.resolve("example.com")
            
            assert ip4 == []
            assert ip6 == []
    
    def test_resolve_handles_timeout(self, dns_resolver):
        """Test handling of DNS timeout."""
        with patch.object(dns_resolver._resolver, 'resolve') as mock_resolve:
            mock_resolve.side_effect = dns.exception.Timeout()
            
            ip4, ip6 = dns_resolver.resolve("slow.example.com")
            
            assert ip4 == []
            assert ip6 == []


class TestResolveDNSFunction:
    """Tests for resolve_dns convenience function."""
    
    def test_function_uses_default_resolver(self):
        """Test that function uses the default resolver."""
        from bot.services.dns import resolve_dns, default_resolver
        
        with patch.object(default_resolver, 'resolve', return_value=([], [])) as mock:
            resolve_dns("example.com")
            mock.assert_called_once_with("example.com")
