"""
Ensure DATABASE_URL exists before fastapi_audit.database is imported (required at import time).
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault(
    "AUDIT_HASH_PEPPER",
    "test-audit-pepper-at-least-32-characters-long",
)
