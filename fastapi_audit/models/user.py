from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastapi_audit.audit import AuditBase, audited


@audited(
    {
        "id": ("ignore", "ignore"),
        "email": ("mask:type=email", "ignore"),
        "name": ("raw", "hash"),
        "phone": ("mask:type=phone", "hash"),
    }
)
class User(AuditBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
