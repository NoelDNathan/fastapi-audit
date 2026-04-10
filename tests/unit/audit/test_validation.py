"""Unit tests for audit configuration validation (SQLAlchemy mapper-aware)."""

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column

from fastapi_audit.models.audit.decorators import audited
from fastapi_audit.models.audit.exceptions import AuditConfigurationError
from fastapi_audit.models.audit.orm import AuditBase
from fastapi_audit.models.audit.validation import (
    validate_audit_config,
    validate_audit_models,
    validate_audit_on_delete,
    validate_on_delete_vs_persist,
)


@audited({
        "id": ("ignore", "ignore"),
        "code": ("raw", "hash"),
})
class SampleAuditedEntity(AuditBase):
    """Sample audited entity for testing."""
    __tablename__ = "unit_test_sample_audited_entity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String)


def test_validate_audit_config_success():
    """Test that the audit configuration is validated successfully."""
    validate_audit_config(
        SampleAuditedEntity,
        {"id": "ignore", "code": "raw"},
    )


def test_validate_audit_config_missing_columns():
    """Test that the validation fails with missing columns."""
    with pytest.raises(AuditConfigurationError, match="missing audit config"):
        validate_audit_config(SampleAuditedEntity, {"id": "ignore"})


def test_validate_audit_config_invalid_strategy():
    """Test that the validation fails with invalid strategies."""
    with pytest.raises(AuditConfigurationError, match="invalid audit strategies"):
        validate_audit_config(
            SampleAuditedEntity,
            {"id": "ignore", "code": "not_a_strategy"},
        )


def test_validate_audit_config_unknown_columns():
    """Persist map must not contain keys that are not mapper columns."""
    with pytest.raises(AuditConfigurationError, match="unknown columns"):
        validate_audit_config(
            SampleAuditedEntity,
            {"id": "ignore", "code": "raw", "ghost": "mask"},
        )


def test_validate_audit_on_delete_missing_columns():
    """Test that the validation fails with missing columns in on_delete."""
    with pytest.raises(AuditConfigurationError, match="missing on_delete columns"):
        validate_audit_on_delete(SampleAuditedEntity, {"id": "ignore"})

def test_validate_audit_config_none_value_strategy():
    """None strategy should be rejected."""

    with pytest.raises(AuditConfigurationError):
        validate_audit_config(
            SampleAuditedEntity,
            {"id": None, "code": "raw"},  # type: ignore
        )

def test_validate_audit_on_delete_unknown_columns():
    """Test that the validation fails with unknown columns in on_delete."""
    with pytest.raises(AuditConfigurationError, match="unknown columns"):
        validate_audit_on_delete(
            SampleAuditedEntity,
            {"id": "ignore", "code": "hash", "ghost": "raw"},
        )


def test_validate_audit_on_delete_invalid_strategy():
    """Test that the validation fails with invalid strategies in on_delete."""
    with pytest.raises(AuditConfigurationError, match="invalid on_delete"):
        validate_audit_on_delete(
            SampleAuditedEntity,
            {"id": "ignore", "code": "bad_strat"},
        )


def test_validate_audit_models_accepts_sample_mapper_only():
    """Use a fake registry so the full global Base.registry need not be audit-valid."""

    class _FakeReg:
        mappers = (sa_inspect(SampleAuditedEntity),)

    validate_audit_models(_FakeReg())  # type: ignore[arg-type]


def test_validate_on_delete_vs_persist_rejects_missing_persist_column():
    """Persist missing column should raise error (explicit validation)."""
    with pytest.raises(AuditConfigurationError, match="missing persist strategy"):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            {},  # persist empty
            {"id": "ignore"},
        )

def test_validate_on_delete_vs_persist_rejects_disjoint_keys():
    """Persist and on_delete must refer to same logical columns."""
    with pytest.raises(AuditConfigurationError):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            {"id": "ignore"},
            {"code": "ignore"},
        )

def test_validate_on_delete_vs_persist_invalid_persist_strategy():
    """Unknown strategy in persist should fail fast."""
    with pytest.raises(KeyError):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            {"id": "does_not_exist"},
            {"id": "ignore"},
        )

def test_validate_on_delete_vs_persist_invalid_on_delete_strategy():
    """Unknown strategy in on_delete should fail fast."""
    with pytest.raises(KeyError):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            {"id": "ignore"},
            {"id": "does_not_exist"},
        )

def test_validate_audit_models_multiple_mappers():
    """Ensure registry iteration handles multiple audited models."""

    class AnotherAuditedEntity(AuditBase):
        """Another audited entity for testing."""
        __tablename__ = "unit_test_other_entity"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        code: Mapped[str] = mapped_column(String)

    AnotherAuditedEntity.__audit_config__ = {
        "id": "ignore",
        "code": "raw",
    }
    AnotherAuditedEntity.__audit_config_on_delete__ = {
        "id": "ignore",
        "code": "raw",
    }

    class _FakeReg:
        mappers = (
            sa_inspect(SampleAuditedEntity),
            sa_inspect(AnotherAuditedEntity),
        )

    validate_audit_models(_FakeReg())  # should not raise

def test_validate_audit_models_ignores_non_audit_base():
    """Non AuditBase models should be skipped."""

    class NotAudited:
        pass

    class _FakeMapper:
        class_ = NotAudited

    class _FakeReg:
        mappers = (_FakeMapper(),)

    validate_audit_models(_FakeReg())  # should not raise

def test_validate_audit_config_empty_dict_rejects():
    """Empty audit config should fail due to missing columns."""

    with pytest.raises(AuditConfigurationError):
        validate_audit_config(SampleAuditedEntity, {})

def test_validate_audit_models_rejects_empty_on_delete_map():
    """On_delete map must not be empty."""

    class BrokenOnDeleteEntity(AuditBase):
        """Broken on_delete entity for testing."""
        __tablename__ = "unit_test_broken_on_delete_entity"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    BrokenOnDeleteEntity.__audit_config__ = {"id": "ignore"}
    BrokenOnDeleteEntity.__audit_config_on_delete__ = {}

    class _FakeReg:
        mappers = (sa_inspect(BrokenOnDeleteEntity),)

    with pytest.raises(AuditConfigurationError, match="must define on_delete"):
        validate_audit_models(_FakeReg())  # type: ignore[arg-type]


# Built-in strictness: ignore > hash > mask > raw. on_delete rank must be >= persist per column.
_ON_DELETE_VS_PERSIST_OK: list[tuple[dict[str, str], dict[str, str]]] = [
    # Same strategy on persist and delete
    ({"id": "ignore", "code": "raw"}, 
     {"id": "ignore", "code": "raw"}),
    
    ({"id": "hash", "code": "mask"}, 
     {"id": "hash", "code": "mask"}),
    
    # Stricter on_delete than persist
    ({"id": "raw", "code": "mask"}, 
     {"id": "hash", "code": "hash"}),
    
    ({"id": "mask", "code": "hash"}, 
     {"id": "hash", "code": "ignore"}),
    
    # Strongest delete for weakest persist
    ({"id": "raw", "code": "raw"}, 
     {"id": "ignore", "code": "ignore"}),
]


@pytest.mark.parametrize(
    ("persist", "on_delete"),
    _ON_DELETE_VS_PERSIST_OK,
    ids=[
        "equal_ignore_raw",
        "equal_hash_mask",
        "stricter_both_columns",
        "stricter_mixed_columns",
        "weakest_persist_strongest_delete",
    ],
)
def test_validate_on_delete_vs_persist_success(
    persist: dict[str, str],
    on_delete: dict[str, str],
):
    """on_delete must be equally or more strict than persist (curated valid pairs)."""
    validate_on_delete_vs_persist(SampleAuditedEntity, persist, on_delete)

_ON_DELETE_VS_PERSIST_BAD: list[tuple[dict[str, str], dict[str, str]]] = [
    (
        {"id": "ignore", "code": "hash"},
        {"id": "ignore", "code": "raw"},
    ),
    (
        {"id": "ignore", "code": "ignore"},
        {"id": "ignore", "code": "hash"},
    ),
    (
        {"id": "ignore", "code": "mask"},
        {"id": "ignore", "code": "raw"},
    ),
    (
        {"id": "ignore", "code": "hash"},
        {"id": "ignore", "code": "mask"},
    ),
    (
        {"id": "mask", "code": "raw"},
        {"id": "raw", "code": "raw"},
    ),
    (
        {"id": "hash", "code": "hash"},
        {"id": "raw", "code": "mask"},
    ),
]


@pytest.mark.parametrize(
    ("persist", "on_delete"),
    _ON_DELETE_VS_PERSIST_BAD,
    ids=[
        "code_hash_vs_raw",
        "code_ignore_vs_hash",
        "code_mask_vs_raw",
        "code_hash_vs_mask",
        "id_mask_vs_raw",
        "multi_column_violations",
    ],
)
def test_validate_on_delete_vs_persist_rejects_weaker_delete(
    persist: dict[str, str],
    on_delete: dict[str, str],
):
    """on_delete strategy must not be weaker than persist (lower strictness rank)."""
    with pytest.raises(AuditConfigurationError, match="at least as strict"):
        validate_on_delete_vs_persist(SampleAuditedEntity, persist, on_delete)


def test_validate_on_delete_vs_persist_none_values_in_strategies():
    """None values in persist or on_delete should raise error."""

    with pytest.raises(AuditConfigurationError, match="missing persist or on_delete strategy"):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            {"id": None, "code": "raw"},
            {"id": "ignore", "code": "raw"},
        )

    with pytest.raises(AuditConfigurationError, match="missing persist or on_delete strategy"):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            {"id": "raw", "code": "raw"},
            {"id": None, "code": "raw"},
        )

class FakeDictWithDuplicateKeys(dict):
    """Fake dictionary with duplicate logical keys."""
    def keys(self):
        # Simulate duplicate logical keys
        return ["id", "id", "code"]  # duplicate artificial


def test_validate_on_delete_vs_persist_duplicate_persist_keys():
    """Persist with duplicate logical keys must raise error."""

    persist = FakeDictWithDuplicateKeys({"id": "raw", "code": "raw"})
    on_delete = {"id": "ignore", "code": "ignore"}

    with pytest.raises(AuditConfigurationError, match="persist must have unique keys"):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            persist,
            on_delete,
        )

class FakeDictWithDuplicateKeysOD(dict):
    def keys(self):
        return ["id", "id", "code"]


def test_validate_on_delete_vs_persist_duplicate_on_delete_keys():
    """On_delete with duplicate logical keys must raise error."""

    persist = {"id": "raw", "code": "raw"}
    on_delete = FakeDictWithDuplicateKeysOD({"id": "ignore", "code": "ignore"})

    with pytest.raises(AuditConfigurationError, match="on_delete must have unique keys"):
        validate_on_delete_vs_persist(
            SampleAuditedEntity,
            persist,
            on_delete,
        )