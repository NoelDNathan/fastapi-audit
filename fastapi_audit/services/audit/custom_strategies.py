"""
Example custom audit strategies. Imported from main before fastapi_audit.models so names exist at validation.

Built-in typed masks (same strictness as ``mask``): ``mask:type=email``, ``mask:type=phone``,
``mask:type=card``, ``mask:type=generic``, or plain ``mask``.

Add project-specific strategies here with register_audit_strategy().
"""

from __future__ import annotations
