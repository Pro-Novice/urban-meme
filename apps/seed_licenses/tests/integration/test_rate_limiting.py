import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient


# =============================================================================
# Helpers
# =============================================================================

SAFE_ENDPOINT = "/api/blockchain/license/count/"   # lightweight GET, no auth needed


def _get(client, path=SAFE_ENDPOINT, remote_addr="1.2.3.4", forwarded_for=None):
    """Send GET with optional X-Forwarded-For header."""
    kwargs = {"SERVER_NAME": "testserver", "REMOTE_ADDR": remote_addr}
    if forwarded_for:
        kwargs["HTTP_X_FORWARDED_FOR"] = forwarded_for
    return client.get(path, **kwargs)


def _burst(client, count, remote_addr="1.2.3.4", forwarded_for=None):
    """Fire `count` rapid requests and return list of status codes."""
    return [
        _get(client, remote_addr=remote_addr, forwarded_for=forwarded_for).status_code
        for _ in range(count)
    ]


def _count_429(codes):
    return sum(1 for c in codes if c == 429)


def _all_ok(codes):
    return all(c in (200, 202) for c in codes)


# =============================================================================
# Layer 1 — DRF AnonRateThrottle  (60 requests / minute)
# =============================================================================

@pytest.mark.django_db
class TestDRFAnonThrottle:
    """AnonRateThrottle: 60/min.  After 60 requests the 61st must be 429."""

    def setup_method(self):
        cache.clear()

    def test_first_60_requests_succeed(self):
        """Requests 1-60 from the same IP must all return non-429."""
        client = APIClient()
        codes = _burst(client, 60, remote_addr="10.0.0.1")
        assert _all_ok(codes), (
            f"Expected all 200/202 for first 60 requests, "
            f"got throttled at: {[i for i,c in enumerate(codes) if c==429]}"
        )

    def test_61st_request_throttled(self):
        """Request 61 from the same IP must return 429."""
        client = APIClient()
        _burst(client, 60, remote_addr="10.0.0.2")   # exhaust quota
        resp = _get(client, remote_addr="10.0.0.2")
        assert resp.status_code == 429, (
            f"Expected 429 on request 61, got {resp.status_code}"
        )

    def test_different_ips_have_independent_quotas(self):
        """Two different IPs must each get their own 60-request quota."""
        client = APIClient()
        # Exhaust IP A
        _burst(client, 60, remote_addr="10.0.1.1")
        assert _get(client, remote_addr="10.0.1.1").status_code == 429

        # IP B still has its full quota
        codes_b = _burst(client, 60, remote_addr="10.0.1.2")
        assert _all_ok(codes_b), "IP B should not be throttled by IP A's usage"

    def test_cache_clear_resets_throttle(self):
        """Clearing the cache resets the throttle counter for an IP."""
        client = APIClient()
        _burst(client, 60, remote_addr="10.0.0.3")
        assert _get(client, remote_addr="10.0.0.3").status_code == 429

        cache.clear()

        resp = _get(client, remote_addr="10.0.0.3")
        assert resp.status_code in (200, 202), (
            "After cache.clear() throttle must reset; "
            f"got {resp.status_code}"
        )


# =============================================================================
# Layer 2 — X-Forwarded-For and NUM_PROXIES=1
# =============================================================================

@pytest.mark.django_db
class TestXForwardedForIPExtraction:

    def setup_method(self):
        cache.clear()

    def test_xff_single_hop_uses_client_ip(self):
        """
        Single trusted proxy: XFF contains only the real client IP.
        Throttle counter should accumulate against the real client IP,
        NOT the proxy IP.
        """
        client = APIClient()
        PROXY_IP   = "172.17.0.1"
        CLIENT_IP  = "203.0.113.5"

        # 60 requests from CLIENT_IP via the proxy
        for _ in range(60):
            _get(client, remote_addr=PROXY_IP, forwarded_for=CLIENT_IP)

        # 61st must be 429 for the CLIENT_IP
        resp = _get(client, remote_addr=PROXY_IP, forwarded_for=CLIENT_IP)
        assert resp.status_code == 429, (
            f"Expected 429 after 60 requests from CLIENT_IP via proxy, "
            f"got {resp.status_code}"
        )

    def test_different_clients_via_same_proxy_independent_quotas(self):
        """
        Two clients routed through the same proxy must have independent quotas.
        The throttle key must be the client IP, not the proxy IP.
        """
        client = APIClient()
        PROXY_IP  = "172.17.0.1"
        CLIENT_A  = "203.0.113.10"
        CLIENT_B  = "203.0.113.20"

        # Exhaust client A's quota
        for _ in range(60):
            _get(client, remote_addr=PROXY_IP, forwarded_for=CLIENT_A)
        assert _get(client, remote_addr=PROXY_IP, forwarded_for=CLIENT_A).status_code == 429

        # Client B (same proxy) must still have its full quota
        codes_b = [
            _get(client, remote_addr=PROXY_IP, forwarded_for=CLIENT_B).status_code
            for _ in range(10)
        ]
        assert _all_ok(codes_b), (
            f"Client B throttled by Client A's usage — proxy IP used as key? "
            f"codes: {codes_b}"
        )

    def test_spoofed_xff_cannot_bypass_throttle(self):
        
        client     = APIClient()
        PROXY_IP   = "172.17.0.1"
        ATTACKER   = "203.0.113.99"
        FAKE_IP    = "1.1.1.1"

        # Exhaust attacker quota — XFF = "attacker_ip" (single hop, legitimate)
        for _ in range(60):
            _get(client, remote_addr=PROXY_IP, forwarded_for=ATTACKER)
        assert _get(client, remote_addr=PROXY_IP, forwarded_for=ATTACKER).status_code == 429

        # Now attacker tries spoofing: XFF = "fake_ip, attacker_ip"
        # The last entry is still ATTACKER so the quota is still exhausted.
        spoofed_xff = f"{FAKE_IP}, {ATTACKER}"
        resp = _get(client, remote_addr=PROXY_IP, forwarded_for=spoofed_xff)
        assert resp.status_code == 429, (
            f"Spoofed XFF bypassed throttle — NUM_PROXIES may not be set correctly. "
            f"Got {resp.status_code} (expected 429)"
        )

    def test_no_xff_falls_back_to_remote_addr(self):
        
        client = APIClient()
        DIRECT_IP = "10.10.10.10"

        codes = _burst(client, 60, remote_addr=DIRECT_IP, forwarded_for=None)
        assert _all_ok(codes)

        resp = _get(client, remote_addr=DIRECT_IP, forwarded_for=None)
        assert resp.status_code == 429, (
            f"Direct connection (no XFF) should still be throttled by REMOTE_ADDR. "
            f"Got {resp.status_code}"
        )


# =============================================================================
# Layer 3 — Nginx rate limit  (10r/s, burst=20, returns 429)
# =============================================================================

@pytest.mark.xfail(
    reason=(
        "Nginx rate limiting cannot be tested inside pytest — "
        "the Nginx process is not part of the Django test server. "
    ),
    strict=False,
)
@pytest.mark.django_db
class TestNginxRateLimitPlaceholder:

    def test_nginx_burst_limit_placeholder(self):
        raise NotImplementedError(
            "Run:  ./scripts/test_rate_limits.sh "
            "http://localhost:8000  to test Nginx rate limiting."
        )