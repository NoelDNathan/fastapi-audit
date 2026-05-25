"""
Argon2id hashing for database passwords and audit redaction.

Passwords: random salt per hash (PHC string stored in DB), verify with verify_password().
Audit: deterministic Argon2id digest (hex) using AUDIT_HASH_PEPPER or SECRET_KEY so the same
value yields the same audit fingerprint within a deployment.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type, hash_secret_raw

# Interactive password storage (OWASP-style defaults via argon2-cffi PasswordHasher)
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Audit: Argon2id with app pepper; tuned lower than login hashes for throughput
_AUDIT_TIME_COST = 2
_AUDIT_MEMORY_COST = 19456
_AUDIT_PARALLELISM = 1
_AUDIT_HASH_LEN = 32
_AUDIT_SALT_BYTES = 16

_DEV_PEPPER = "fastapi-audit-dev-pepper-not-for-production-use-only"


@lru_cache(maxsize=1)
def _audit_pepper() -> str:
    pepper = os.environ.get("AUDIT_HASH_PEPPER") or os.environ.get("SECRET_KEY")
    if pepper and len(pepper) >= 16:
        return pepper
    if os.environ.get("ENVIRONMENT") == "production":
        raise RuntimeError(
            "Set AUDIT_HASH_PEPPER or SECRET_KEY (at least 16 characters) for audit hashing"
        )
    return _DEV_PEPPER


def _audit_salt_bytes() -> bytes:
    """Deterministic salt per deployment derived from the audit pepper."""
    material = f"fastapi-audit:argon2id:v1:{_audit_pepper()}"
    return hashlib.sha256(material.encode()).digest()[:_AUDIT_SALT_BYTES]


def reset_audit_hash_config() -> None:
    """Clear cached pepper (for tests or settings reload)."""
    _audit_pepper.cache_clear()


def hash_password(plain_password: str) -> str:
    """
    Hash a password for database storage.

    Returns a PHC-encoded Argon2id string (includes random salt). Use verify_password() to check.
    """
    return _PASSWORD_HASHER.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if plain_password matches the stored PHC hash."""
    try:
        _PASSWORD_HASHER.verify(password_hash, plain_password)
        return True
    except VerifyMismatchError:
        return False


def hash_audit_value(value: str) -> str:
    """
    Deterministic Argon2id hex digest for audit ``hash`` strategy.

    Same plaintext always produces the same digest for a given pepper/deployment.
    """
    digest = hash_secret_raw(
        secret=value.encode("utf-8"),
        salt=_audit_salt_bytes(),
        time_cost=_AUDIT_TIME_COST,
        memory_cost=_AUDIT_MEMORY_COST,
        parallelism=_AUDIT_PARALLELISM,
        hash_len=_AUDIT_HASH_LEN,
        type=Type.ID,
    )
    return digest.hex()
