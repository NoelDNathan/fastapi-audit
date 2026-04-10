from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from fastapi_audit.database import get_db
from fastapi_audit.schemas.user import UserSchema
from fastapi_audit.services import user as user_service

router = APIRouter()


@router.get("/", response_model=list[UserSchema])
async def list_users(db: Session = Depends(get_db)):
    return user_service.list_users(db)


@router.get("/{user_id}", response_model=UserSchema)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    return user_service.get_user(user_id, db)


@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def add_user(user: UserSchema, db: Session = Depends(get_db)):
    return user_service.create_user(user, db)


@router.put("/{user_id}", response_model=UserSchema)
async def replace_user(user_id: int, user: UserSchema, db: Session = Depends(get_db)):
    return user_service.update_user(user_id, user, db)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(user_id: int, db: Session = Depends(get_db)):
    user_service.delete_user(user_id, db)
