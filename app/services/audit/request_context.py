"""
Audit metadata attached to the SQLAlchemy Session (session.info).

Using session.info instead of ContextVar so values are visible in the same
session/flush as ORM listeners when FastAPI runs sync dependencies in a
worker thread (ContextVar tokens do not reliably match across those boundaries).
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address

AUDIT_SESSION_INFO_KEY = "audit_request_context"

DEFAULT_CHANGED_BY = "anonymous"
FALLBACK_CHANGED_BY = "system"

ClientIPAddress = IPv4Address | IPv6Address


@dataclass(frozen=True, slots=True)
class AuditRequestContext:
    """Audit metadata attached to the SQLAlchemy Session (session.info)."""
    changed_by: str
    ip_address: ClientIPAddress | None
