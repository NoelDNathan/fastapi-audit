from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastapi_audit.audit import AuditBase, audited


@audited(
    {
        "id": ("ignore", "ignore"),
        "title": ("raw", "hash"),
        "author": ("mask", "ignore"),
        "description": ("mask", "ignore"),
        "rating": ("hash", "ignore"),
    }
)
class Book(AuditBase):
    """
    Model for the books table
    """

    __tablename__ = "books"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    rating: Mapped[int] = mapped_column(Integer)
