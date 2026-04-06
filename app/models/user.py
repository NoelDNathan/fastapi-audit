from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.audit import AuditBase, audited


@audited(
    {
        "id": ("ignore", "ignore"),
        "email": ("mask", "ignore"),
        "name": ("raw", "hash"),
        "phone": ("phone_last4", "hash"),
    }
)
class User(AuditBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
