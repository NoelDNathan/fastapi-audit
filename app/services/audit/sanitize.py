"""
Audit value transforms and strategy registry.

Built-in strategies: ignore, hash, mask, raw (each has a strictness rank).
Register custom strategies with register_audit_strategy(name, fn, strictness=...).
Higher strictness = stronger hiding; on_delete strategy must be >= persist strictness.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

AuditTransform = Callable[[Any], Any]

# name -> (callable | None for ignore-like, strictness int; higher = stricter)
_registry: dict[str, tuple[AuditTransform | None, int]] = {}


def mask(value: Any) -> Any:
    """Replace scalar with a fixed mask."""
    if value is None:
        return None
    return "***"


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
    _registry["mask"] = (mask, 500)
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
    """All strategy names known to the registry (built-ins + custom)."""
    return frozenset(_registry.keys())


def strategy_strictness(name: str) -> int:
    """Return strictness rank for comparisons (on_delete vs persist)."""
    if name not in _registry:
        raise KeyError(f"unknown audit strategy: {name!r}")
    return _registry[name][1]


def sanitize(strategy: str, value: Any) -> Any:
    """Apply a named audit strategy to a value for change snapshots."""
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
        return _registry[key][1]

    def __iter__(self):
        return iter(_registry)

    def __len__(self) -> int:
        return len(_registry)

    def __contains__(self, key: object) -> bool:
        return key in _registry


VALID_STRATEGIES: Mapping[str, int] = MappingProxyType(_StrictnessView())
