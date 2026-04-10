"""Unit tests for audit strategy registry and sanitize()."""

import hashlib

import pytest
from fastapi_audit.services.audit.sanitize import VALID_STRATEGIES
from fastapi_audit.services.audit import sanitize as sanitize_mod
from fastapi_audit.services.audit.sanitize import (
    hash_value,
    mask,
    raw,
    register_audit_strategy,
    registered_strategy_names,
    sanitize,
    strategy_strictness,
)


@pytest.fixture(autouse=True)
def reset_audit_strategies():
    """Restore built-in strategies after each test (custom registration is global)."""
    yield
    sanitize_mod._install_builtins()


def test_mask_none_and_scalar():
    """Test mask function."""
    assert mask(None) is None
    assert mask("secret") == "***"
    assert mask(42) == "***"


def test_hash_value_none_and_scalar():
    """Test hash_value function."""
    assert hash_value(None) is None
    expected = hashlib.sha256(b"hello").hexdigest()
    assert hash_value("hello") == expected


def test_raw_passthrough():
    """Test raw function."""
    assert raw(None) is None
    assert raw({"a": 1}) == {"a": 1}


def test_sanitize_builtins():
    """Test sanitize function."""
    assert sanitize("ignore", "x") is None
    assert sanitize("mask", "x") == "***"
    assert sanitize("hash", "x") == hashlib.sha256(b"x").hexdigest()
    assert sanitize("raw", "y") == "y"


def test_sanitize_unknown_strategy_falls_back_to_raw():
    """Test sanitize function falls back to raw when strategy is unknown."""
    assert sanitize("not_a_registered_name", "keep") == "keep"


def test_strategy_strictness_known():
    """Test strategy_strictness function."""
    assert strategy_strictness("ignore") > strategy_strictness("hash")
    assert strategy_strictness("hash") > strategy_strictness("mask")
    assert strategy_strictness("mask") > strategy_strictness("raw")


def test_strategy_strictness_unknown_raises():
    """Test strategy_strictness function raises error when strategy is unknown."""
    with pytest.raises(KeyError, match="unknown audit strategy"):
        strategy_strictness("nonexistent_strategy_xyz")


def test_registered_strategy_names_includes_builtins():
    """Test registered_strategy_names function includes built-ins."""
    names = registered_strategy_names()
    assert {"ignore", "hash", "mask", "raw"}.issubset(names)


def test_register_audit_strategy_custom():
    """Test register_audit_strategy function registers a custom strategy."""
    def double(x):
        return x * 2 if x is not None else None

    register_audit_strategy("double_it", double, strictness=200)
    assert sanitize("double_it", 3) == 6
    assert strategy_strictness("double_it") == 200


def test_register_audit_strategy_ignore_like():
    """Test register_audit_strategy function registers an ignore-like strategy."""
    register_audit_strategy("omit_field", None, strictness=900)
    assert sanitize("omit_field", "anything") is None


def test_register_audit_strategy_validation():
    """Test register_audit_strategy function validates the strategy name."""
    with pytest.raises(ValueError, match="non-empty"):
        register_audit_strategy("", raw, strictness=1)

    with pytest.raises(ValueError, match="alphanumeric"):
        register_audit_strategy("bad-name", raw, strictness=1)

    register_audit_strategy("once", raw, strictness=1)
    with pytest.raises(ValueError, match="already registered"):
        register_audit_strategy("once", raw, strictness=2)

    register_audit_strategy("once", mask, strictness=5, override=True)
    assert sanitize("once", "v") == "***"

    with pytest.raises(ValueError, match=">= 0"):
        register_audit_strategy("neg", raw, strictness=-1)


def test_register_audit_strategy_strips_name():
    """Test register_audit_strategy function strips the strategy name."""
    register_audit_strategy("  spaced  ", raw, strictness=10)
    assert "spaced" in registered_strategy_names()
    assert sanitize("spaced", 1) == 1


def test_phone_last4_custom_strategy():
    """Test phone_last4 custom strategy."""
    import fastapi_audit.services.audit.custom_strategies  # noqa: F401 — registers phone_last4

    assert sanitize("phone_last4", "+1 (555) 123-4567") == "***4567"
    assert sanitize("phone_last4", "12") == "***"
    assert sanitize("phone_last4", None) is None

def test_registry_is_reset_between_tests():
    """Test registry is reset between tests."""
    register_audit_strategy("temp", raw, strictness=1)
    assert "temp" in registered_strategy_names()


def test_registry_does_not_leak():
    """Test registry does not leak between tests."""
    assert "temp" not in registered_strategy_names()

# ====================================================================================
# VALID_STRATEGIES tests
# ====================================================================================

def test_valid_strategies_is_read_only():
    """Test valid_strategies is read only."""
    with pytest.raises(TypeError):
        VALID_STRATEGIES["new"] = 123  # type: ignore
    
    with pytest.raises(TypeError):
        del VALID_STRATEGIES["mask"]  # type: ignore


def test_valid_strategies_matches_registry():
    """Test valid_strategies matches registry."""
    for name in registered_strategy_names():
        assert name in VALID_STRATEGIES
        assert VALID_STRATEGIES[name] == strategy_strictness(name)

def test_strictness_view_getitem_matches_strategy_strictness():
    """Test strictness view getitem matches strategy strictness."""
    for name in VALID_STRATEGIES:
        assert VALID_STRATEGIES[name] == strategy_strictness(name)


def test_strictness_view_len_matches_registry():
    """Test strictness view length matches registry."""
    assert len(VALID_STRATEGIES) == len(set(VALID_STRATEGIES))


def test_strictness_view_iterates_all_keys():
    """Test strictness view iterates all keys."""
    keys = set(iter(VALID_STRATEGIES))
    assert keys == set(VALID_STRATEGIES.keys())


def test_strictness_view_contains():
    """Test strictness view contains built-ins."""
    assert "mask" in VALID_STRATEGIES
    assert "hash" in VALID_STRATEGIES
    assert "nonexistent" not in VALID_STRATEGIES


def test_strictness_view_keyerror_on_missing():
    """Test strictness view raises KeyError on missing."""
    with pytest.raises(KeyError):
        _ = VALID_STRATEGIES["does_not_exist"]


def test_strictness_view_reflects_new_registrations():
    """Test strictness view reflects new registrations."""
    register_audit_strategy("custom_x", lambda x: x, strictness=123)

    assert "custom_x" in VALID_STRATEGIES
    assert VALID_STRATEGIES["custom_x"] == 123


def test_strictness_view_reflects_override():
    """Test strictness view reflects override."""
    register_audit_strategy("override_me", lambda x: x, strictness=100)
    assert VALID_STRATEGIES["override_me"] == 100

    register_audit_strategy("override_me", lambda x: None, strictness=900, override=True)
    assert VALID_STRATEGIES["override_me"] == 900

