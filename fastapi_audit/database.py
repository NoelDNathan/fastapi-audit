import os

from dotenv import load_dotenv
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from fastapi_audit.utils.audit_session import attach_audit_request_context

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db(request: Request):
    db = SessionLocal()
    attach_audit_request_context(db, request)
    try:
        yield db
    finally:
        db.close()
