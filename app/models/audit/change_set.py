from sqlalchemy.inspection import inspect as sa_inspect

from app.models.audit.exceptions import AuditConfigurationError
from app.services.audit.sanitize import sanitize


DEFAULT_STRATEGY = "ignore"


def get_strategy(model_cls, key, mode="persist") -> str:
    """
    Get the strategy for the given key.
    """
    if mode == "delete":
        overrides = getattr(model_cls, "__audit_config_on_delete__", None)
        if overrides is None:
            raise AuditConfigurationError("__audit_config_on_delete__ is None")
        if key in overrides:
            return overrides[key]

    config = getattr(model_cls, "__audit_config__", None)
    if config is None:
        raise AuditConfigurationError("__audit_config__ is None")

    return config.get(key, DEFAULT_STRATEGY)


def any_on_delete_strategy_differs(model_cls) -> bool:
    """
    Check if any on_delete strategy differs from the persist strategy.
    """
    persist = getattr(model_cls, "__audit_config__", None) or {}
    on_delete = getattr(model_cls, "__audit_config_on_delete__", None) or {}
    for key in on_delete:
        if on_delete[key] != persist.get(key, DEFAULT_STRATEGY):
            return True
    return False


def changes_for_update(obj) -> dict:
    """Build change snapshot for an updated instance."""
    state = sa_inspect(obj)
    config = getattr(obj.__class__, "__audit_config__", {})
    changes = {}
    for attr in state.attrs:
        hist = attr.history
        if not hist.has_changes():
            continue
        key = attr.key
        strategy = config.get(key, DEFAULT_STRATEGY)
        if strategy == "ignore":
            continue
        old = hist.deleted[0] if hist.deleted else None
        new = hist.added[0] if hist.added else None
        changes[key] = {
            "old": sanitize(strategy, old),
            "new": sanitize(strategy, new),
        }
    return changes


def changes_for_insert(obj) -> dict:
    """Build change snapshot for a new instance."""
    state = sa_inspect(obj)
    config = getattr(obj.__class__, "__audit_config__", {})
    changes = {}
    for col in state.mapper.column_attrs:
        key = col.key
        strategy = config.get(key, DEFAULT_STRATEGY)
        if strategy == "ignore":
            continue
        val = getattr(obj, key, None)
        changes[key] = {"new": sanitize(strategy, val)}
    return changes


def changes_for_delete(obj) -> dict:
    """Build change snapshot for a deleted instance."""
    state = sa_inspect(obj)
    model_cls = obj.__class__
    changes = {}
    for col in state.mapper.column_attrs:
        key = col.key
        strategy = get_strategy(model_cls, key, mode="delete")
        if strategy == "ignore":
            continue
        val = getattr(obj, key, None)
        changes[key] = {"old": sanitize(strategy, val), "new": None}
    return changes


def resanitize_changes_for_delete(changes: dict, model_cls) -> dict:
    """
    Re-sanitize stored audit payloads for delete policy. If on_delete matches persist for a
    field, values are already final; re-applying would break idempotent strategies (e.g. hash).
    """
    out: dict = {}
    for key, payload in changes.items():
        delete_strat = get_strategy(model_cls, key, mode="delete")
        if delete_strat == "ignore":
            continue
        if not isinstance(payload, dict):
            continue
        persist_strat = get_strategy(model_cls, key, mode="persist")
        if delete_strat == persist_strat:
            entry = {k: payload[k] for k in ("old", "new") if k in payload}
            if entry:
                out[key] = entry
            continue
        entry = {}
        if "old" in payload:
            entry["old"] = sanitize(delete_strat, payload["old"])
        if "new" in payload:
            entry["new"] = sanitize(delete_strat, payload["new"])
        if entry:
            out[key] = entry
    return out
