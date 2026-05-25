"""Tests for Argon2 password and audit hashing."""

import pytest

from fastapi_audit.security.argon2_hash import (
    hash_audit_value,
    hash_password,
    reset_audit_hash_config,
    verify_password,
)


@pytest.fixture(autouse=True)
def _reset_pepper_cache():
    reset_audit_hash_config()
    yield
    reset_audit_hash_config()


def test_hash_password_verify_roundtrip():
    """Password hashes use random salt and verify correctly."""
    stored = hash_password("s3cret!")
    assert stored.startswith("$argon2")
    assert verify_password("s3cret!", stored)
    assert not verify_password("wrong", stored)


def test_hash_audit_value_deterministic():
    """Audit digests are stable for the same value (test pepper from conftest)."""
    a = hash_audit_value("same")
    b = hash_audit_value("same")
    c = hash_audit_value("other")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_hash_audit_value_changes_with_pepper(monkeypatch):
    """Different peppers produce different audit digests."""
    monkeypatch.setenv("AUDIT_HASH_PEPPER", "pepper-one-16chars-min!!")
    reset_audit_hash_config()
    one = hash_audit_value("x")

    monkeypatch.setenv("AUDIT_HASH_PEPPER", "pepper-two-16chars-min!!")
    reset_audit_hash_config()
    two = hash_audit_value("x")

    assert one != two
