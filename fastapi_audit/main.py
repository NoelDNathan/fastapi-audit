from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

import app.services.audit.custom_strategies  # noqa: F401 — register custom audit strategies first
import app.models  # noqa: F401 — register ORM models on Base.metadata
from app.audit import validate_audit_models
from app.database import Base, engine
from app.panels.audit_panel import router as audit_panel_router
from app.routers import book as book_router
from app.routers import user as user_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_audit_models(Base.registry)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="FastAPI Template",
    description="HTTP API with interactive OpenAPI documentation.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


app.include_router(book_router.router, prefix="/books", tags=["books"])
app.include_router(user_router.router, prefix="/users", tags=["users"])
app.include_router(audit_panel_router)
