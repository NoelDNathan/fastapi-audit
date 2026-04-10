from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from fastapi_audit.database import get_db
from fastapi_audit.schemas.book import BookSchema
from fastapi_audit.services import book as book_service

router = APIRouter()


@router.get("/", response_model=list[BookSchema])
async def list_books(db: Session = Depends(get_db)):
    return book_service.list_books(db)


@router.post("/", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
async def add_book(book: BookSchema, db: Session = Depends(get_db)):
    return book_service.create_book(book, db)


@router.put("/{book_id}", response_model=BookSchema)
async def replace_book(book_id: int, book: BookSchema, db: Session = Depends(get_db)):
    return book_service.update_book(book_id, book, db)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_book(book_id: int, db: Session = Depends(get_db)):
    book_service.delete_book(book_id, db)
