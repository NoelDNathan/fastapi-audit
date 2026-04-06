from sqlalchemy.inspection import inspect 
from sqlalchemy.orm import registry as Registry

from app.models.audit.exceptions import AuditConfigurationError
from app.models.audit.orm import AuditBase
from app.services.audit.sanitize import VALID_STRATEGIES


def _validate_mapping_keys_match_columns(
    cls,
    mapping: dict[str, str],
    *,
    missing_label: str,
    extra_label: str,
) -> None:
    """Require mapping keys to match mapper columns exactly (no missing, no extra)."""
    mapper = inspect(cls)
    columns = {c.key for c in mapper.column_attrs}
    cls_name = cls.__name__

    keys = set(mapping.keys())
    missing = columns - keys
    if missing:
        raise AuditConfigurationError(f"{cls_name} missing {missing_label}: {missing}")
    extra = keys - columns
    if extra:
        raise AuditConfigurationError(f"{cls_name} {extra_label}: {extra}")


def validate_strategies(
    config: dict[str, str],
    cls,
    *,
    invalid_label: str = "invalid audit strategies",
) -> None:
    """Validate that every strategy name is registered."""
    cls_name = cls.__name__
    invalid = {
        k: v
        for k, v in config.items()
        if v not in VALID_STRATEGIES
    }
    if invalid:
        raise AuditConfigurationError(f"{cls_name} {invalid_label}: {invalid}")


def validate_audit_config(cls, config: dict[str, str]) -> None:
    """Validate the audit configuration for the given class."""

    _validate_mapping_keys_match_columns(
        cls,
        config,
        missing_label="audit config",
        extra_label="audit config references unknown columns",
    )
    validate_strategies(config, cls)


def validate_audit_on_delete(cls, on_delete: dict[str, str]) -> None:
    """Validate the on_delete configuration for the given class."""

    _validate_mapping_keys_match_columns(
        cls,
        on_delete,
        missing_label="on_delete columns",
        extra_label="on_delete references unknown columns",
    )
    validate_strategies(on_delete, cls, invalid_label="invalid on_delete strategies")


def validate_on_delete_vs_persist(
    cls,
    persist: dict[str, str],
    on_delete: dict[str, str],
) -> None:
    """
    on_delete must be equally or more strict than persist (higher strictness rank wins).
    Built-ins: ignore (1000) > hash (800) > mask (500) > raw (100). Custom strategies
    use ranks chosen at registration; on_delete rank must be >= persist rank per column.

    Every persist key must appear in on_delete. Keys present only in on_delete are treated
    as persist strategy 'raw' when persist is non-empty; an entirely empty persist map
    with a non-empty on_delete map is rejected (missing explicit persist strategy).
    """
    violations: list[str] = []
    cls_name = cls.__name__

    if len(persist.keys()) != len(set(persist.keys())):
        raise AuditConfigurationError(f"{cls_name} persist must have unique keys")

    if len(on_delete.keys()) != len(set(on_delete.keys())):
        raise AuditConfigurationError(f"{cls_name} on_delete must have unique keys")

    persist_keys = set(persist.keys())
    on_delete_keys = set(on_delete.keys())

    only_in_persist = persist_keys - on_delete_keys
    if only_in_persist:
        cols = ", ".join(sorted(only_in_persist))
        raise AuditConfigurationError(f"{cls_name} missing on_delete strategy for columns: {cols}")

    only_in_on_delete = on_delete_keys - persist_keys
    if only_in_on_delete:
        cols = ", ".join(sorted(only_in_on_delete))
        raise AuditConfigurationError(f"{cls_name} missing persist strategy for columns: {cols}")

    for key in sorted(on_delete_keys):
        p_val = persist.get(key, "raw")
        d_val = on_delete[key]
        if p_val is None or d_val is None:
            raise AuditConfigurationError(
                f"{cls_name} missing persist or on_delete strategy for column {key!r}"
            )

        p_rank = VALID_STRATEGIES[p_val]
        d_rank = VALID_STRATEGIES[d_val]
        if d_rank < p_rank:
            violations.append(f"{key}: persist={p_val!r}, on_delete={d_val!r}")
    if violations:
        raise AuditConfigurationError(
            f"{cls_name} on_delete must be at least as strict as persist "
            f"(strictest to weakest: ignore, hash, mask, raw). Offenders: "
            f"{'; '.join(violations)}"
        )


def validate_audit_models(reg: Registry) -> None:
    """After all models are imported, ensure every AuditBase subclass defines a full column map."""
    for mapper in reg.mappers:
        cls = mapper.class_
        if not issubclass(cls, AuditBase):
            continue
        config = getattr(cls, "__audit_config__", None) or {}
        validate_audit_config(cls, config)
        on_delete = getattr(cls, "__audit_config_on_delete__", None) or {}
        if not on_delete:
            raise AuditConfigurationError(
                f"{cls.__name__} must define on_delete for every column "
                f"(use @audited({{...}}) with a tuple per column)"
            )
        validate_audit_on_delete(cls, on_delete)
        validate_on_delete_vs_persist(cls, config, on_delete)
