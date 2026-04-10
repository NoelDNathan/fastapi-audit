from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from fastapi_audit.database import Base


class AuditBase(Base):
    """Abstract base: subclasses are real tables and must define __audit_config__ (e.g. via @audited)."""

    __abstract__ = True
    __audit_config__: Mapping[str, str] = {}
    __audit_config_on_delete__: Mapping[str, str] = {}


class Audit(Base):
    """ORM audit log row for entity changes."""

    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String)
    headers: Mapped[list[str]] = mapped_column("headers", ARRAY(String))
    method: Mapped[str] = mapped_column(String)
    response: Mapped[str] = mapped_column(String)
    changed_by: Mapped[str] = mapped_column(String)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ip_address: Mapped[str] = mapped_column(String)
