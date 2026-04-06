"""
Entity audit ORM: models, @audited decorator, validation, and session listeners.

Importing this package registers SQLAlchemy before_flush / after_flush_postexec listeners.

Call register_audit_strategy() before importing models that reference custom strategy names
in @audited (e.g. at the top of main.py, before `import app.models`).
"""

from app.models.audit.decorators import audited
from app.models.audit.exceptions import AuditConfigurationError
from app.models.audit.orm import Audit, AuditBase
from app.models.audit.validation import (
    validate_audit_config,
    validate_audit_models,
    validate_audit_on_delete,
    validate_on_delete_vs_persist,
)
from app.services.audit.sanitize import (
    register_audit_strategy,
    registered_strategy_names,
    strategy_strictness,
)

# Register session listeners (side effect on import).
from . import session_listeners as _session_listeners  # noqa: F401

__all__ = [
    "Audit",
    "AuditBase",
    "AuditConfigurationError",
    "audited",
    "register_audit_strategy",
    "registered_strategy_names",
    "strategy_strictness",
    "validate_audit_config",
    "validate_audit_models",
    "validate_audit_on_delete",
    "validate_on_delete_vs_persist",
]
