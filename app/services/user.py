from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserSchema


def _normalize_phone(phone: str | None) -> str | None:
    if phone is None:
        return None
    stripped = phone.strip()
    return stripped or None


def list_users(db: Session):
    rows = db.query(User).order_by(User.id).all()
    return [UserSchema.model_validate(u) for u in rows]


def get_user(user_id: int, db: Session) -> UserSchema:
    row = db.query(User).filter(User.id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"User id {user_id} does not exist")
    return UserSchema.model_validate(row)


def create_user(data: UserSchema, db: Session):
    existing = db.query(User).filter(User.email == str(data.email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    row = User(
        email=str(data.email).strip().lower(),
        name=data.name.strip(),
        phone=_normalize_phone(data.phone),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserSchema.model_validate(row)


def update_user(user_id: int, data: UserSchema, db: Session):
    row = db.query(User).filter(User.id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"User id {user_id} does not exist")

    new_email = str(data.email).strip().lower()
    if new_email != row.email:
        taken = db.query(User).filter(User.email == new_email, User.id != user_id).first()
        if taken is not None:
            raise HTTPException(status_code=409, detail="Email already registered")

    row.email = new_email
    row.name = data.name.strip()
    row.phone = _normalize_phone(data.phone)
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserSchema.model_validate(row)


def delete_user(user_id: int, db: Session):
    row = db.query(User).filter(User.id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"User id {user_id} does not exist")
    db.delete(row)
    db.commit()
