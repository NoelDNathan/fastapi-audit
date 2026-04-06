"""Unit tests for @audited decorator."""

# pylint: disable=missing-class-docstring,missing-function-docstring,unnecessary-pass,too-few-public-methods

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from app.models.audit.decorators import audited


def get_audited_class_mappings(
    cls: type,
) -> tuple[Mapping[str, str], Mapping[str, str]]:
    """Return persist and on_delete audit mappings from a class; raise if either is missing."""
    persist = getattr(cls, "__audit_config__", None)
    on_delete = getattr(cls, "__audit_config_on_delete__", None)
    if persist is None:
        raise ValueError("__audit_config__ is not set")
    if on_delete is None:
        raise ValueError("__audit_config_on_delete__ is not set")
    return persist, on_delete


def test_audited_sets_class_attributes():
    """Test that the @audited decorator sets the class attributes correctly."""

    @audited(
        {
            "id": ("ignore", "ignore"),
            "email": ("mask", "hash"),
        }
    )
    class Example:
        pass

    audit_config, audit_config_on_delete = get_audited_class_mappings(Example)

    assert audit_config == {"id": "ignore", "email": "mask"}
    assert audit_config_on_delete == {"id": "ignore", "email": "hash"}


def test_audited_sets_immutability():
    @audited(
        {
            "id": ("ignore", "ignore"),
            "email": ("mask", "hash"),
        }
    )
    class Example:
        pass

    with pytest.raises(TypeError, match="does not support item assignment"):
        Example.__audit_config__["email"] = "ignore"  # type: ignore[index]

    with pytest.raises(TypeError, match="does not support item assignment"):
        Example.__audit_config_on_delete__["id"] = "mask"  # type: ignore[index]

    audit_config, audit_config_on_delete = get_audited_class_mappings(Example)

    assert audit_config == {"id": "ignore", "email": "mask"}
    assert audit_config_on_delete == {"id": "ignore", "email": "hash"}

    assert isinstance(audit_config, MappingProxyType)
    assert isinstance(audit_config_on_delete, MappingProxyType)


def test_input_dict_is_copied():
    """Test that the input dictionary is copied."""
    columns = {"id": ("ignore", "ignore")}

    @audited(columns)
    class Example:
        pass

    columns["id"] = ("changed", "changed")

    audit_config, audit_config_on_delete = get_audited_class_mappings(Example)

    assert audit_config == {"id": "ignore"}
    assert audit_config_on_delete == {"id": "ignore"}


def test_audited_rejects_empty_dict():
    """Test that the @audited decorator rejects an empty dictionary."""
    with pytest.raises(TypeError, match="non-empty dict"):
        audited({})(object)


def test_audited_rejects_non_dict():
    """Test that the @audited decorator rejects a non-dictionary."""
    with pytest.raises(TypeError, match="non-empty dict"):
        audited("not_a_dict")(object)  # type: ignore[arg-type]


def test_audited_rejects_invalid_column_mapping():
    """Test that the @audited decorator rejects an invalid column mapping."""
    with pytest.raises(TypeError, match="must map to"):
        audited({"col": "mask"})(object)  # type: ignore[dict-item]

    with pytest.raises(TypeError, match="must map to"):
        audited({"col": ("only_one",)})(object)  # type: ignore[dict-item]


def test_audited_rejects_double_application():
    """Stacked @audited on the same class must fail (inner runs first, outer would overwrite)."""
    with pytest.raises(TypeError, match="twice"):

        @audited({"a": ("raw", "hash")})
        @audited({"b": ("mask", "ignore")})
        class _DuplicateAudited:
            pass

    class X:
        pass

    X = audited({"c": ("raw", "hash")})(X)
    with pytest.raises(TypeError, match="twice"):
        X = audited({"d": ("mask", "ignore")})(X)

    audit_config, audit_config_on_delete = get_audited_class_mappings(X)
    assert audit_config == {"c": "raw"}
    assert audit_config_on_delete == {"c": "hash"}


def test_audited_as_function():
    """Test that the @audited decorator can be used as a function."""
    decorator = audited({"id": ("ignore", "ignore")})

    class Example:
        pass

    result = decorator(Example)

    audit_config, audit_config_on_delete = get_audited_class_mappings(result)

    assert audit_config == {"id": "ignore"}
    assert audit_config_on_delete == {"id": "ignore"}


def test_returns_same_class_instance():
    """Test that the @audited decorator returns the same class instance."""
    decorator = audited({"id": ("ignore", "ignore")})

    class Example:
        pass

    original = Example
    result = decorator(Example)

    assert result is original


def test_multiple_decorators_are_isolated():
    """Test that multiple @audited decorators are isolated."""

    @audited({"a": ("p1", "d1")})
    class A:
        pass

    @audited({"b": ("p2", "d2")})
    class B:
        pass

    a_config, _ = get_audited_class_mappings(A)
    b_config, _ = get_audited_class_mappings(B)

    assert a_config == {"a": "p1"}
    assert b_config == {"b": "p2"}


def test_subclass_can_be_audited_independently():
    """Test that a subclass can be audited independently."""

    @audited({"a": ("p1", "d1")})
    class Base:
        pass

    class Child(Base):
        pass

    child = audited({"b": ("p2", "d2")})(Child)

    persist, on_delete = get_audited_class_mappings(child)
    assert persist == {"b": "p2"}
    assert on_delete == {"b": "d2"}


def test_subclass_can_be_audited_independently_with_multiple_decorators():
    """Test that a subclass can be audited independently with multiple decorators."""

    @audited({"a": ("p1", "d1")})
    class Base:
        pass

    @audited({"b": ("p2", "d2")})
    class Child(Base):
        pass

    persist, on_delete = get_audited_class_mappings(Child)
    assert persist == {"b": "p2"}
    assert on_delete == {"b": "d2"}


def test_hierarchy_is_preserved():
    """Test that the hierarchy is preserved."""

    @audited({"a": ("p1", "d1")})
    class Base:
        pass

    class Child(Base):
        pass

    persist, on_delete = get_audited_class_mappings(Child)
    assert persist == {"a": "p1"}
    assert on_delete == {"a": "d1"}

    persist, on_delete = get_audited_class_mappings(Base)
    assert persist == {"a": "p1"}
    assert on_delete == {"a": "d1"}


@pytest.mark.parametrize(
    "invalid_value",
    [
        "string",
        ("only_one",),
        ("a", "b", "c"),
        123,
        None,
    ],
)
def test_invalid_column_values(invalid_value):
    """Test that the @audited decorator rejects invalid column values."""
    with pytest.raises(TypeError):
        audited({"col": invalid_value})(object)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "string",
        ("only_one",),
        ("a", "b", "c"),
        123,
        None,
    ],
)
def test_invalid_on_delete_values(invalid_value):
    """Test that the @audited decorator rejects invalid on_delete values."""
    with pytest.raises(TypeError):
        audited({"col": ("ignore", invalid_value)})(object)


@pytest.mark.parametrize(
    "invalid_key",
    [
        ("only_one",),
        ("a", "b", "c"),
        123,
        None,
    ],
)
def test_invalid_column_keys(invalid_key):
    """Test that the @audited decorator rejects invalid column keys."""
    with pytest.raises(TypeError):
        audited({invalid_key: ("ignore", "ignore")})(object)
