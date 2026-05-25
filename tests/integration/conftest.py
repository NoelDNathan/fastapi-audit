"""
Integration tests: PostgreSQL via Testcontainers.

Run in isolation so ``fastapi_audit.database`` is first imported with the container URL::

    pytest tests/integration -v

Do not run ``pytest tests`` in one process if ``tests/unit`` imports ``fastapi_audit.database``
first (SQLite); integration needs a fresh interpreter with only this path collected.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Generator

import pytest
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

def _sqlalchemy_psycopg2_url(url: str) -> str:
    """Convert a PostgreSQL URL to a SQLAlchemy URL."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


@pytest.fixture(scope="session", autouse=True)
def _postgres_schema() -> Generator[None, None, None]:
    """Fixture to create a database schema."""
    with PostgresContainer("postgres:15-alpine") as postgres:
        os.environ["DATABASE_URL"] = _sqlalchemy_psycopg2_url(
            postgres.get_connection_url()
        )
        os.environ.setdefault(
            "AUDIT_HASH_PEPPER",
            "test-audit-pepper-at-least-32-characters-long",
        )
        importlib.import_module("fastapi_audit.services.audit.custom_strategies")
        importlib.import_module("fastapi_audit.database")
        importlib.import_module("fastapi_audit.models.audit")
        importlib.import_module("fastapi_audit.models.books")
        importlib.import_module("fastapi_audit.models.user")

        from fastapi_audit.database import Base, engine

        Base.metadata.create_all(engine)
        yield


@pytest.fixture
def db_session(_postgres_schema):  # noqa: ARG001 — ensures schema exists
    """Fixture to get a database session."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from fastapi_audit.database import engine

    Session = sessionmaker(bind=engine)
    session = Session()
    for stmt in (
        text("DELETE FROM audit"),
        text("DELETE FROM books"),
        text("DELETE FROM users"),
    ):
        session.execute(stmt)
    session.commit()
    try:
        yield session
    finally:
        for stmt in (
            text("DELETE FROM audit"),
            text("DELETE FROM books"),
            text("DELETE FROM users"),
        ):
            session.execute(stmt)
        session.commit()
        session.close()


@pytest.fixture
def User_model(_postgres_schema):  # noqa: ARG001
    """Fixture to get the User model."""
    from fastapi_audit.models.user import User

    return User
