"""
Audit value transforms and strategy registry.

Built-in strategies: ignore, hash, mask, raw (each has a strictness rank).
Parameterized masks use the same rank as ``mask``: ``mask:type=email``,
``mask:type=phone``, ``mask:type=card``, ``mask:type=generic`` (or plain ``mask``).

Register custom strategies with register_audit_strategy(name, fn, strictness=...).
Higher strictness = stronger hiding; on_delete strategy must be >= persist strictness.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

AuditTransform = Callable[[Any], Any]

MASK_STRICTNESS = 500
_MASK_TYPE_PREFIX = "mask:type="
_MASK_TYPE_PATTERN = re.compile(r"^mask:type=([a-z][a-z0-9_]*)$")

# name -> (callable | None for ignore-like, strictness int; higher = stricter)
_registry: dict[str, tuple[AuditTransform | None, int]] = {}

_BUILTIN_MASK_TYPES = frozenset({"generic", "email", "phone", "card"})


def mask(value: Any) -> Any:
    """Replace scalar with a fixed mask (generic)."""
    if value is None:
        return None
    return "***"


def mask_email(value: Any) -> Any:
    """Keep first local character and domain; mask the rest of the local part."""
    if value is None:
        return None
    text = str(value).strip()
    if "@" not in text:
        return mask(text)
    local, _, domain = text.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(value: Any) -> Any:
    """Store phone as ***XXXX using the last four digits; non-digits stripped."""
    if value is None:
        return None
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_card(value: Any) -> Any:
    """Keep last four digits of a card number; non-digits stripped."""
    if value is None:
        return None
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


_MASK_TYPE_TRANSFORMS: dict[str, AuditTransform] = {
    "generic": mask,
    "email": mask_email,
    "phone": mask_phone,
    "card": mask_card,
}


def parse_mask_strategy(name: str) -> str | None:
    """
    Return mask type if *name* is ``mask`` or ``mask:type=<type>``, else None.

    Unknown or malformed mask parameterizations return None (invalid strategy).
    """
    if not isinstance(name, str):
        return None
    if name == "mask":
        return "generic"
    match = _MASK_TYPE_PATTERN.match(name)
    if not match:
        return None
    mask_type = match.group(1)
    if mask_type in _BUILTIN_MASK_TYPES:
        return mask_type
    return None


def is_valid_strategy(name: str) -> bool:
    """True if *name* is a registered strategy or a built-in mask parameterization."""
    if not isinstance(name, str):
        return False
    if name in _registry:
        return True
    return parse_mask_strategy(name) is not None


def mask_strategy_names() -> frozenset[str]:
    """All built-in mask strategy spellings (plain mask + mask:type=*)."""
    typed = frozenset(f"{_MASK_TYPE_PREFIX}{t}" for t in sorted(_BUILTIN_MASK_TYPES))
    return frozenset({"mask"}) | typed


def hash_value(value: Any) -> Any:
    """SHA-256 hex digest of str(value)."""
    if value is None:
        return None
    return hashlib.sha256(str(value).encode()).hexdigest()


def raw(value: Any) -> Any:
    """Persist value unchanged."""
    return value


def _install_builtins() -> None:
    _registry.clear()
    # Strictness: higher = stricter. Custom strategies should pick values in this scale
    # (e.g. between mask 500 and hash 800) so on_delete vs persist checks make sense.
    _registry["ignore"] = (None, 1000)
    _registry["hash"] = (hash_value, 800)
    _registry["mask"] = (mask, MASK_STRICTNESS)
    _registry["raw"] = (raw, 100)


_install_builtins()


def register_audit_strategy(
    name: str,
    fn: AuditTransform | None,
    *,
    strictness: int,
    override: bool = False,
) -> None:
    """
    Register a custom audit strategy.

    :param name: Identifier used in @audited({...}) and column configs. Use snake_case.
    :param fn: Transform for insert/update/delete snapshots; None means omit field (like ignore).
    :param strictness: Non-negative integer; higher = stricter. on_delete must use strictness
        greater than or equal to persist for the same column.
    :param override: If True, replace an existing strategy with the same name.
    """
    if not name or not str(name).strip():
        raise ValueError("strategy name must be non-empty")
    name = str(name).strip()
    if parse_mask_strategy(name) is not None:
        raise ValueError(
            f"strategy name {name!r} is reserved for built-in mask parameterizations"
        )
    if not name.replace("_", "").isalnum():
        raise ValueError(
            f"strategy name {name!r} must be alphanumeric with underscores only"
        )
    if name in _registry and not override:
        raise ValueError(
            f"audit strategy {name!r} is already registered (use override=True to replace)"
        )
    if strictness < 0:
        raise ValueError("strictness must be >= 0")
    _registry[name] = (fn, strictness)


def registered_strategy_names() -> frozenset[str]:
    """All strategy names in the registry (built-ins + custom)."""
    return frozenset(_registry.keys())


def strategy_strictness(name: str) -> int:
    """Return strictness rank for comparisons (on_delete vs persist)."""
    if parse_mask_strategy(name) is not None:
        return MASK_STRICTNESS
    if name not in _registry:
        raise KeyError(f"unknown audit strategy: {name!r}")
    return _registry[name][1]


def sanitize(strategy: str, value: Any) -> Any:
    """Apply a named audit strategy to a value for change snapshots."""
    mask_type = parse_mask_strategy(strategy)
    if mask_type is not None:
        return _MASK_TYPE_TRANSFORMS[mask_type](value)

    entry = _registry.get(strategy)
    if entry is None:
        return raw(value)
    fn, _rank = entry
    if fn is None:
        return None
    return fn(value)


# --- Public read-only view: single source for validation and strictness ranks ---


class _StrictnessView(Mapping[str, int]):
    def __getitem__(self, key: str) -> int:
        if parse_mask_strategy(key) is not None:
            return MASK_STRICTNESS
        return _registry[key][1]

    def __iter__(self):
        return iter(_registry)

    def __len__(self) -> int:
        return len(_registry)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        if key in _registry:
            return True
        return parse_mask_strategy(key) is not None


VALID_STRATEGIES: Mapping[str, int] = MappingProxyType(_StrictnessView())
