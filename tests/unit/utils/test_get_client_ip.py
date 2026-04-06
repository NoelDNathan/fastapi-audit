"""Unit tests for client IP extraction from FastAPI Request headers."""

from ipaddress import IPv4Address, IPv6Address

import pytest
from fastapi import Request

from app.utils.get_client_ip import _extract_ip, get_client_ip


def _make_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str | None = "127.0.0.1",
) -> Request:
    hdrs: list[tuple[bytes, bytes]] = []
    if headers:
        for key, value in headers.items():
            hdrs.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    scope: dict = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "scheme": "http",
        "server": ("testserver", 80),
        "headers": hdrs,
    }
    if client_host is not None:
        scope["client"] = (client_host, 12345)
    else:
        scope["client"] = None
    return Request(scope)


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "\t"],
    ids=["empty", "spaces", "tab"],
)
def test_extract_ip_empty_or_whitespace(raw: str):
    """Test extract_ip returns None for empty or whitespace input."""
    assert _extract_ip(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("127.0.0.1", IPv4Address("127.0.0.1")),
        ("  8.8.8.8  ", IPv4Address("8.8.8.8")),
        ("192.168.0.1:8080", IPv4Address("192.168.0.1")),
        ("[::1]", IPv6Address("::1")),
        ("[2001:db8::1]", IPv6Address("2001:db8::1")),
        ("::1", IPv6Address("::1")),
        ("fe80::1%eth0", IPv6Address("fe80::1")),
    ],
    ids=[
        "v4_plain",
        "v4_stripped",
        "v4_with_port",
        "v6_bracket_loopback",
        "v6_bracket_doc",
        "v6_plain",
        "v6_zone_id_stripped",
    ],
)
def test_extract_ip_valid(raw: str, expected: IPv4Address | IPv6Address):
    """Test extract_ip returns the expected IP address."""
    assert _extract_ip(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "not-an-ip",
        "999.999.999.999",
        "[notv6]",
        "[::1",  # missing closing bracket
        "host:name:8080",  # two colons, not host:port v4 pattern
    ],
    ids=["garbage", "invalid_v4", "bracket_garbage", "unclosed_bracket", "multi_colon"],
)
def test_extract_ip_invalid(raw: str):
    """Test extract_ip returns None for invalid IP addresses."""
    assert _extract_ip(raw) is None

def test_get_client_ip_x_forwarded_for_leftmost():
    """Test get_client_ip uses leftmost x-forwarded-for entry."""
    req = _make_request(headers={"x-forwarded-for": "203.0.113.1, 198.51.100.2"})
    assert get_client_ip(req) == IPv4Address("203.0.113.1")


def test_get_client_ip_x_forwarded_for_skips_invalid_then_valid():
    """Test get_client_ip skips invalid x-forwarded-for entries then uses valid one."""
    req = _make_request(headers={"x-forwarded-for": "bogus, 198.51.100.10"})
    assert get_client_ip(req) == IPv4Address("198.51.100.10")


def test_get_client_ip_x_forwarded_for_all_invalid_falls_through():
    """Test get_client_ip falls through to client host when all x-forwarded-for entries are invalid."""
    req = _make_request(
        headers={"x-forwarded-for": "not-an-ip, also-bad", "x-real-ip": "10.0.0.1"},
        client_host="192.168.1.1",
    )
    assert get_client_ip(req) == IPv4Address("10.0.0.1")


def test_get_client_ip_prefers_x_forwarded_for_over_x_real_ip():
    """Test get_client_ip prefers x-forwarded-for over x-real-ip."""
    req = _make_request(
        headers={"x-forwarded-for": "203.0.113.5", "x-real-ip": "10.0.0.1"},
    )
    assert get_client_ip(req) == IPv4Address("203.0.113.5")


def test_get_client_ip_x_real_ip_when_no_xff():
    """Test get_client_ip uses x-real-ip when no x-forwarded-for is present."""
    req = _make_request(headers={"x-real-ip": "  172.16.0.1  "})
    assert get_client_ip(req) == IPv4Address("172.16.0.1")


def test_get_client_ip_forwarded_header():
    """Test get_client_ip extracts IPv6 address from forwarded header."""
    req = _make_request(
        headers={"forwarded": 'for="[2001:db8::42]";proto=https'},
    )
    assert get_client_ip(req) == IPv6Address("2001:db8::42")


def test_get_client_ip_forwarded_ignores_non_for_segments():
    """Test get_client_ip ignores non-for segments in forwarded header."""
    req = _make_request(
        headers={"forwarded": "proto=http; for=192.0.2.1"},
    )
    assert get_client_ip(req) == IPv4Address("192.0.2.1")


def test_get_client_ip_uses_client_host_when_no_proxy_headers():
    """Test get_client_ip uses client host when no proxy headers are present."""
    req = _make_request(headers={}, client_host="10.10.10.10")
    assert get_client_ip(req) == IPv4Address("10.10.10.10")


def test_get_client_ip_none_when_no_usable_source():
    """Test get_client_ip returns None when no usable source is available."""
    req = _make_request(headers={}, client_host=None)
    assert get_client_ip(req) is None

def test_get_client_ip_x_real_ip_invalid_does_not_block_fallback():
    """
    If x-real-ip is invalid, it must NOT block fallback to request.client.host.
    """
    req = _make_request(
        headers={
            "x-real-ip": "not-a-valid-ip"
        },
        client_host="192.168.1.100",
    )

    assert get_client_ip(req) == IPv4Address("192.168.1.100")