"""Bind audit request metadata to a SQLAlchemy session (session.info)."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.services.audit.request_context import (
    AUDIT_SESSION_INFO_KEY,
    DEFAULT_CHANGED_BY,
    AuditRequestContext,
)
from app.utils.get_client_ip import get_client_ip


def attach_audit_request_context(
    session: Session | AsyncSession,
    request: Request,
) -> None:
    """Store ``AuditRequestContext`` on ``session.info`` for ORM audit listeners.

    Accepts a synchronous :class:`~sqlalchemy.orm.Session` or an
    :class:`~sqlalchemy.ext.asyncio.AsyncSession`; both use the same ``info`` map.
    """
    session.info[AUDIT_SESSION_INFO_KEY] = AuditRequestContext(
        changed_by=DEFAULT_CHANGED_BY,
        ip_address=get_client_ip(request),
    )
