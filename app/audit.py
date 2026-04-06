"""
Public audit API for this package and for editable installs in other projects.

Prefer importing from here instead of deep paths (e.g. ``app.models.audit.decorators``)::

    from app.audit import (
        audited,
        AuditBase,
        Audit,
        attach_audit_request_context,
        validate_audit_models,
        register_audit_strategy,
    )

Importing this module registers ORM session listeners (via :mod:`app.models.audit`).

``app.database`` keeps a direct import of :func:`app.utils.audit_session.attach_audit_request_context`
to avoid a circular import with :mod:`app.models.audit`; consumers should still import attach from
``app.audit``.
"""

from __future__ import annotations

from app.models.audit import (
    Audit,
    AuditBase,
    AuditConfigurationError,
    audited,
    register_audit_strategy,
    registered_strategy_names,
    strategy_strictness,
    validate_audit_config,
    validate_audit_models,
    validate_audit_on_delete,
    validate_on_delete_vs_persist,
)
from app.services.audit.request_context import (
    AUDIT_SESSION_INFO_KEY,
    DEFAULT_CHANGED_BY,
    FALLBACK_CHANGED_BY,
    AuditRequestContext,
    ClientIPAddress,
)
from app.services.audit.sanitize import VALID_STRATEGIES, sanitize
from app.utils.audit_session import (
    attach_audit_request_context,
    set_audit_request_context,
)

__all__ = [
    "AUDIT_SESSION_INFO_KEY",
    "DEFAULT_CHANGED_BY",
    "FALLBACK_CHANGED_BY",
    "Audit",
    "AuditBase",
    "AuditConfigurationError",
    "AuditRequestContext",
    "ClientIPAddress",
    "VALID_STRATEGIES",
    "attach_audit_request_context",
    "audited",
    "register_audit_strategy",
    "registered_strategy_names",
    "sanitize",
    "set_audit_request_context",
    "strategy_strictness",
    "validate_audit_config",
    "validate_audit_models",
    "validate_audit_on_delete",
    "validate_on_delete_vs_persist",
]
