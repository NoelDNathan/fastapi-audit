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


def set_audit_request_context(
    session: Session | AsyncSession,
    context: AuditRequestContext,
) -> None:
    """Attach an explicit :class:`AuditRequestContext` (jobs, scripts, tests).

    For HTTP handlers prefer :func:`attach_audit_request_context`.
    """
    session.info[AUDIT_SESSION_INFO_KEY] = context


def attach_audit_request_context(
    session: Session | AsyncSession,
    request: Request,
    *,
    changed_by: str | None = None,
) -> None:
    """Store ``AuditRequestContext`` on ``session.info`` for ORM audit listeners.

    Accepts a synchronous :class:`~sqlalchemy.orm.Session` or an
    :class:`~sqlalchemy.ext.asyncio.AsyncSession`; both use the same ``info`` map.

    :param changed_by: Actor label (e.g. user id). Defaults to :data:`DEFAULT_CHANGED_BY`.
    """
    set_audit_request_context(
        session,
        AuditRequestContext(
            changed_by=changed_by if changed_by is not None else DEFAULT_CHANGED_BY,
            ip_address=get_client_ip(request),
        ),
    )
