from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Book
from app.schemas.book import BookSchema


def list_books(db: Session):
    """
    List all books in the database.
    """
    rows = db.query(Book).all()
    return [BookSchema.model_validate(b) for b in rows]


def create_book(data: BookSchema, db: Session):
    """
    Create a new book in the database.
    """
    book_model = Book(
        title=data.title,
        author=data.author,
        description=data.description,
        rating=data.rating,
    )
    db.add(book_model)
    db.commit()
    db.refresh(book_model)
    return BookSchema.model_validate(book_model)


def update_book(book_id: int, data: BookSchema, db: Session):
    """
    Update a book in the database.
    """
    book_model = db.query(Book).filter(Book.id == book_id).first()

    if book_model is None:
        raise HTTPException(
            status_code=404,
            detail=f"ID {book_id} : Does not exist",
        )

    book_model.title = data.title
    book_model.author = data.author
    book_model.description = data.description
    book_model.rating = data.rating

    db.add(book_model)
    db.commit()
    db.refresh(book_model)

    return BookSchema.model_validate(book_model)


def delete_book(book_id: int, db: Session):
    """
    Delete a book from the database.
    """
    book_model = db.query(Book).filter(Book.id == book_id).first()

    if book_model is None:
        raise HTTPException(
            status_code=404,
            detail=f"ID {book_id} : Does not exist",
        )
    db.delete(book_model)
    db.commit()
