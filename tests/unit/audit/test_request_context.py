"""Unit tests for audit request context types and constants."""

from dataclasses import FrozenInstanceError, asdict
import ipaddress

import pytest

from app.services.audit.request_context import (
    AUDIT_SESSION_INFO_KEY,
    DEFAULT_CHANGED_BY,
    FALLBACK_CHANGED_BY,
    AuditRequestContext,
)

# Sample literals for parametrized IPv4 / IPv6 coverage
_IP_SINGLE = (
    "127.0.0.1",
    "1.1.1.1",
    "0.0.0.0",
    "::1",
    "2001:db8::1",
    "fe80::1",
)

# Pairs (initial, other) same IP version for frozen-field reassignment tests
_IP_FROZEN_PAIRS = (
    ("127.0.0.1", "10.0.0.1"),
    ("1.1.1.1", "8.8.8.8"),
    ("::1", "2001:db8::1"),
    ("fe80::1", "fe80::2"),
)

# Pairs for overwrite-in-session tests (first context replaced by second)
_IP_OVERWRITE_PAIRS = (
    ("1.1.1.1", "2.2.2.2"),
    ("2001:db8::1", "2001:db8::2"),
)


def test_session_info_key_is_stable():
    """Test that the session info key is stable."""
    assert AUDIT_SESSION_INFO_KEY == "audit_request_context"


@pytest.mark.parametrize("ip_literal", _IP_SINGLE, ids=lambda s: s)
def test_audit_request_context_fields(ip_literal: str):
    """Test that the AuditRequestContext fields are set correctly."""
    addr = ipaddress.ip_address(ip_literal)
    ctx = AuditRequestContext(changed_by="user-1", ip_address=addr)
    assert ctx.changed_by == "user-1"
    assert ctx.ip_address == addr


@pytest.mark.parametrize(
    ("initial", "other"),
    _IP_FROZEN_PAIRS,
    ids=[
        "v4-loop_to_private",
        "v4-public_to_public",
        "v6-loop_to_doc",
        "v6-linklocal_to_linklocal",
    ],
)
def test_audit_request_context_is_frozen(initial: str, other: str):
    """Test that the AuditRequestContext is frozen (IPv4 and IPv6)."""
    ctx = AuditRequestContext(
        changed_by="a",
        ip_address=ipaddress.ip_address(initial),
    )
    with pytest.raises(FrozenInstanceError):
        ctx.changed_by = "c"
    with pytest.raises(FrozenInstanceError):
        ctx.ip_address = ipaddress.ip_address(other)


@pytest.mark.parametrize("ip_literal", _IP_SINGLE, ids=lambda s: s)
def test_audit_request_context_has_slots(ip_literal: str):
    """Unknown attributes cannot be set on a slotted frozen dataclass."""
    addr = ipaddress.ip_address(ip_literal)
    ctx = AuditRequestContext(changed_by="user1", ip_address=addr)

    with pytest.raises((AttributeError, TypeError)):
        ctx.new_attr = "boom"


@pytest.mark.parametrize("ip_literal", _IP_SINGLE, ids=lambda s: s)
def test_audit_request_context_equality(ip_literal: str):
    """Test that two contexts with the same fields compare equal."""
    addr = ipaddress.ip_address(ip_literal)
    a = AuditRequestContext("user", addr)
    b = AuditRequestContext("user", addr)

    assert a == b


def test_session_info_constants():
    """Test that the session info constants are set correctly."""
    assert isinstance(AUDIT_SESSION_INFO_KEY, str)
    assert DEFAULT_CHANGED_BY == "anonymous"
    assert FALLBACK_CHANGED_BY == "system"


class FakeSession:
    def __init__(self):
        self.info = {}


@pytest.mark.parametrize("ip_literal", _IP_SINGLE, ids=lambda s: s)
def test_context_stored_in_session_info(ip_literal: str):
    """Test that the AuditRequestContext is stored in the session info."""
    session = FakeSession()
    addr = ipaddress.ip_address(ip_literal)
    ctx = AuditRequestContext("user", addr)
    session.info[AUDIT_SESSION_INFO_KEY] = ctx

    assert session.info[AUDIT_SESSION_INFO_KEY] is ctx


@pytest.mark.parametrize(
    ("first", "second"),
    _IP_OVERWRITE_PAIRS,
    ids=["v4_overwrite", "v6_overwrite"],
)
def test_context_overwrite_in_session_info(first: str, second: str):
    """Test that the AuditRequestContext is overwritten in the session info."""
    session = FakeSession()

    ctx1 = AuditRequestContext("user1", ipaddress.ip_address(first))
    ctx2 = AuditRequestContext("user2", ipaddress.ip_address(second))

    session.info[AUDIT_SESSION_INFO_KEY] = ctx1
    session.info[AUDIT_SESSION_INFO_KEY] = ctx2

    assert session.info[AUDIT_SESSION_INFO_KEY] is ctx2


@pytest.mark.parametrize("ip_literal", _IP_SINGLE, ids=lambda s: s)
def test_serialization(ip_literal: str):
    """Test that the AuditRequestContext can be serialized with asdict."""
    addr = ipaddress.ip_address(ip_literal)
    ctx = AuditRequestContext("user", addr)

    data = asdict(ctx)

    assert data == {
        "changed_by": "user",
        "ip_address": addr,
    }


def test_context_allows_none_ip():
    """When the client IP cannot be parsed, ip_address may be None."""
    ctx = AuditRequestContext(changed_by="u", ip_address=None)
    assert ctx.ip_address is None

def test_ip_address_type_enforced():
    """Test that the ip_address is enforced to be an IPv4 or IPv6 address."""
    ctx = AuditRequestContext(
        changed_by="user",
        ip_address=ipaddress.ip_address("127.0.0.1"),
    )

    assert isinstance(ctx.ip_address, (ipaddress.IPv4Address, ipaddress.IPv6Address))

@pytest.mark.parametrize("value", ["", None])
def test_changed_by_edge_cases(value):
    """Test that the changed_by is enforced to be a string."""
    ctx = AuditRequestContext(
        changed_by=value if value is not None else "anonymous",
        ip_address=ipaddress.ip_address("127.0.0.1"),
    )
    assert ctx.changed_by == (value if value is not None else "anonymous")

def test_serialization_with_none_ip():
    """Test that the serialization with none ip_address is handled correctly."""
    ctx = AuditRequestContext("user", None)
    data = asdict(ctx)

    assert data["ip_address"] is None


def test_session_stores_reference_not_copy():
    """Test that the session stores a reference to the AuditRequestContext not a copy."""
    session = FakeSession()
    ctx = AuditRequestContext("user", ipaddress.ip_address("127.0.0.1"))

    session.info[AUDIT_SESSION_INFO_KEY] = ctx

    with pytest.raises(FrozenInstanceError):
        session.info[AUDIT_SESSION_INFO_KEY].changed_by = "x"  

    assert session.info[AUDIT_SESSION_INFO_KEY] is ctx

def test_context_can_be_used_in_set():
    """Test that the AuditRequestContext can be used in a set."""
    ctx = AuditRequestContext("user", ipaddress.ip_address("127.0.0.1"))
    s = {ctx}
    assert ctx in s

def test_context_is_hashable():
    """Test that the AuditRequestContext is hashable."""
    ctx = AuditRequestContext("user", ipaddress.ip_address("127.0.0.1"))
    assert hash(ctx) is not None

def test_ip_address_is_immutable_object():
    """Test that the ip_address is an immutable object."""
    ip = ipaddress.ip_address("127.0.0.1")
    ctx = AuditRequestContext("user", ip)

    with pytest.raises(AttributeError):
        ip.packed = b"\x00\x00\x00\x00"  # read-only property
    
    with pytest.raises(AttributeError):
        ip.compressed = "9.9.9.9"  
 