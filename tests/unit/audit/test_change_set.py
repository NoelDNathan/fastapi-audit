"""Unit tests for audit change snapshot helpers."""

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.audit.change_set import (
    any_on_delete_strategy_differs,
    changes_for_insert,
    resanitize_changes_for_delete,
    get_strategy,
)
from app.models.audit.decorators import audited
from app.models.audit.orm import AuditBase
from app.models.audit.exceptions import AuditConfigurationError
from app.services.audit.sanitize import hash_value



class DummyModel:
    __audit_config__ = {
        "create": "log",
        "update": "track",
    }
    __audit_config_on_delete__ = {
        "delete": "hard_delete"
    }

class EmptyModel:
    pass


class NoneConfigModel:
    __audit_config__ = None
    __audit_config_on_delete__ = None



# =========================
# Parametrized tests
# =========================

@pytest.mark.parametrize(
    "model, key, mode, expected",
    [
        # -------- Happy path --------
        (DummyModel, "create", "persist", "log"),
        (DummyModel, "update", "persist", "track"),
        (DummyModel, "missing", "persist", "ignore"),

        (DummyModel, "delete", "delete", "hard_delete"),
        (DummyModel, "unknown", "delete", "ignore"),

        # -------- Edge cases: fallback behavior --------
        (DummyModel, "create", "delete", "log"),  # fallback to persist config
        (DummyModel, "missing", "delete", "ignore"),

        # -------- Edge cases: invalid mode (treated as persist) --------
        (DummyModel, "create", "something_weird", "log"),
        (DummyModel, "missing", "something_weird", "ignore"),

        # -------- Edge cases: empty key --------
        (type("M", (), {"__audit_config__": {"": "empty"}}),
         "",
         "persist",
         "empty"),

        # -------- Edge cases: numeric key --------
        (type("M", (), {"__audit_config__": {1: "one"}}),
         1,
         "persist",
         "one"),
    ],
)
def test_get_strategy_edge_cases(model, key, mode, expected):
    """Test get_strategy covering happy paths and edge cases."""
    assert get_strategy(model, key, mode=mode) == expected

@pytest.mark.parametrize("model, key, mode", [
    (NoneConfigModel, "create", "persist"),
    (NoneConfigModel, "create", "delete"),

    (EmptyModel, "anything", "persist"),
    (EmptyModel, "anything", "delete"),
])
def test_get_strategy_raises_error_when_config_is_none(model, key, mode):
    """Test get_strategy raises error when config is none."""
    with pytest.raises(AuditConfigurationError, match=" is None"):
        get_strategy(model, key, mode=mode)

# ====================================================================================
# any_on_delete_strategy_differs tests
# ====================================================================================

def test_any_on_delete_strategy_differs():
    """Test any_on_delete_strategy_differs function."""
    class Same:
        __audit_config__ = {"x": "raw"}
        __audit_config_on_delete__ = {"x": "raw"}

    assert any_on_delete_strategy_differs(Same) is False

    class Diff:
        __audit_config__ = {"x": "raw"}
        __audit_config_on_delete__ = {"x": "hash"}

    assert any_on_delete_strategy_differs(Diff) is True

def test_any_on_delete_strategy_differs_empty_on_delete():
    class M:
        __audit_config__ = {"x": "raw"}
        __audit_config_on_delete__ = {}

    assert any_on_delete_strategy_differs(M) is False


def test_any_on_delete_strategy_differs_missing_attr():
    class M:
        __audit_config__ = {"x": "raw"}

    assert any_on_delete_strategy_differs(M) is False


# ====================================================================================
# resanitize_changes_for_delete tests
# ====================================================================================


def test_resanitize_skips_when_delete_matches_persist():
    """Test resanitize_changes_for_delete skips when delete matches persist."""
    class M:
        __audit_config__ = {"token": "hash"}
        __audit_config_on_delete__ = {"token": "hash"}

    payload = {"token": {"old": "pre_hashed_value", "new": None}}
    out = resanitize_changes_for_delete(payload, M)
    assert out["token"]["old"] == "pre_hashed_value"


def test_resanitize_reapplies_when_delete_stricter_than_persist():
    """Test resanitize_changes_for_delete reapplies when delete is stricter than persist."""
    class M:
        __audit_config__ = {"secret": "raw"}
        __audit_config_on_delete__ = {"secret": "hash"}

    payload = {"secret": {"old": "plain", "new": None}}
    out = resanitize_changes_for_delete(payload, M)
    assert out["secret"]["old"] == hash_value("plain")


def test_resanitize_skips_ignore_strategy():
    """Test resanitize_changes_for_delete skips when delete is ignore."""
    class M:
        __audit_config__ = {"x": "raw"}
        __audit_config_on_delete__ = {"x": "ignore"}

    assert resanitize_changes_for_delete({"x": {"old": "v", "new": None}}, M) == {}


def test_resanitize_skips_non_dict_payload_entries():
    """Test resanitize_changes_for_delete skips when payload is not a dict."""
    class M:
        __audit_config__ = {"x": "raw"}
        __audit_config_on_delete__ = {"x": "hash"}

    assert resanitize_changes_for_delete({"x": "not_a_dict"}, M) == {}


def test_resanitize_mixed_payload():
    """Test resanitize_changes_for_delete skips when payload is not a dict."""
    class M:
        __audit_config__ = {"x": "raw"}
        __audit_config_on_delete__ = {"x": "hash"}

    payload = {
        "x": {"old": "a", "new": "b"},
        "y": {"old": "skip_me", "new": None},  
    }

    out = resanitize_changes_for_delete(payload, M)

    assert "x" in out
    assert "y" not in out

# ====================================================================================
# changes_for_insert tests
# ====================================================================================

@audited(
    {
        "id": ("ignore", "ignore"),
        "title": ("mask", "hash"),
    }
)
class RowForInsert(AuditBase):
    __tablename__ = "unit_test_change_set_insert_row"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)


def test_changes_for_insert_transient_instance():
    """Test changes_for_insert for a transient instance."""
    obj = RowForInsert(id=1, title="hello")
    changes = changes_for_insert(obj)
    assert "id" not in changes
    assert changes["title"]["new"] == "***"
