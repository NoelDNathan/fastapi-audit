from __future__ import annotations

from types import MappingProxyType


def audited(columns: dict[str, tuple[str, str]]):
    """
    Register audit strategies per column. Each value is
    (strategy_for_insert_and_update, strategy_on_delete).
    on_delete must be equally or more strict than persist (see register_audit_strategy strictness).

    Built-in masks: ``mask`` (generic ***), or ``mask:type=email``, ``mask:type=phone``,
    ``mask:type=card``, ``mask:type=name``, ``mask:type=generic`` — all share the same
    strictness as ``mask``.

    __audit_config__ and __audit_config_on_delete__ are read-only mappings (MappingProxyType).

    Applying @audited more than once to the same class raises TypeError; use a single dict with
    all columns instead of stacking decorators.
    """
    if not isinstance(columns, dict) or not columns:
        raise TypeError(
            "audited() expects a non-empty dict: column -> (persist, on_delete)"
        )

    field_strategies: dict[str, str] = {}
    on_delete: dict[str, str] = {}
    for key, pair in columns.items():
        if not (isinstance(pair, tuple) and len(pair) == 2):
            raise TypeError(
                f"audited: column {key!r} must map to "
                f"(persist_strategy, on_delete_strategy), got {pair!r}"
            )
        field_strategies[key] = pair[0]
        on_delete[key] = pair[1]

    def wrapper(cls):
        if "__audited_decorator_applied__" in cls.__dict__:
            raise TypeError(
                "@audited cannot be applied twice to the same class; "
                "pass all columns in one @audited({...}) mapping."
            )
        cls.__audit_config__ = MappingProxyType(field_strategies)
        cls.__audit_config_on_delete__ = MappingProxyType(on_delete)
        cls.__audited_decorator_applied__ = True
        return cls

    return wrapper
