"""
Example custom audit strategies. Imported from main before fastapi_audit.models so names exist at validation.

phone_last4: keeps only the last 4 digits, prefixed with *** (stricter than raw, weaker than full mask).
"""

from __future__ import annotations

from typing import Any

from fastapi_audit.services.audit.sanitize import register_audit_strategy


def audit_phone_last4(value: Any) -> Any:
    """Store phone as ***XXXX using the last four digits; non-digits stripped."""
    if value is None:
        return None
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


register_audit_strategy("phone_last4", audit_phone_last4, strictness=450)
