"""
Embedded audit viewer: Jinja2 templates + HTMX for filters, table refresh, and detail pane.
Read-only; wire authentication at the app level when exposing this route.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from fastapi_audit.database import get_db
from fastapi_audit.models.audit import Audit

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "panels"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin/audit", tags=["audit-panel"])

PAGE_SIZE = 25
TIMELINE_MAX_EVENTS = 250


def _parse_response_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"_value": data}
    except json.JSONDecodeError:
        return {"_parse_error": True, "raw": raw}


def _build_list_query(
    *,
    method: str | None,
    entity: str | None,
    entity_id: str | None,
) -> Any:
    stmt = select(Audit).order_by(Audit.id.desc())
    conditions = []

    if method:
        conditions.append(Audit.method == method.strip().upper())

    entity_f = entity.strip() if entity and entity.strip() else None
    entity_id_f = entity_id.strip() if entity_id and entity_id.strip() else None
    if entity_f is not None or entity_id_f is not None:
        j = cast(Audit.response, JSONB)
        if entity_f is not None:
            conditions.append(j["entity"].as_string() == entity_f)
        if entity_id_f is not None:
            conditions.append(j["entity_id"].as_string() == entity_id_f)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    return stmt


def _timeline_rows(
    db: Session,
    *,
    entity: str,
    entity_id: str,
) -> tuple[list[Audit], bool]:
    j = cast(Audit.response, JSONB)
    stmt = (
        select(Audit)
        .where(
            j["entity"].as_string() == entity,
            j["entity_id"].as_string() == entity_id,
        )
        .order_by(Audit.id.asc())
        .limit(TIMELINE_MAX_EVENTS + 1)
    )
    rows = list(db.scalars(stmt).all())
    truncated = len(rows) > TIMELINE_MAX_EVENTS
    if truncated:
        rows = rows[:TIMELINE_MAX_EVENTS]
    return rows, truncated


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def audit_panel_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={"page_size": PAGE_SIZE},
    )


@router.get("/table", response_class=HTMLResponse, include_in_schema=False)
def audit_table_fragment(
    request: Request,
    db: Session = Depends(get_db),
    method: str | None = Query(None, description="INSERT, UPDATE, or DELETE"),
    entity: str | None = Query(None),
    entity_id: str | None = Query(None),
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    stmt = _build_list_query(method=method, entity=entity, entity_id=entity_id)
    offset = (page - 1) * PAGE_SIZE
    rows = list(db.scalars(stmt.offset(offset).limit(PAGE_SIZE + 1)).all())
    has_next = len(rows) > PAGE_SIZE
    if has_next:
        rows = rows[:PAGE_SIZE]

    return templates.TemplateResponse(
        request=request,
        name="audit_table.html",
        context={
            "rows": rows,
            "page": page,
            "has_next": has_next,
            "has_prev": page > 1,
            "parse_payload": _parse_response_payload,
        },
    )


@router.get("/meta/entities", response_class=HTMLResponse, include_in_schema=False)
def audit_entity_options(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Distinct entity names from JSON payload (PostgreSQL)."""
    j = cast(Audit.response, JSONB)
    label = j["entity"].as_string()
    stmt = (
        select(label)
        .distinct()
        .where(label.isnot(None))
        .where(label != "")
        .order_by(label.asc())
        .limit(80)
    )
    names = [r for r in db.scalars(stmt).all() if r]

    return templates.TemplateResponse(
        request=request,
        name="audit_entity_options.html",
        context={"entities": names},
    )


@router.get("/timeline/view", response_class=HTMLResponse, include_in_schema=False)
def audit_timeline_view(
    request: Request,
    db: Session = Depends(get_db),
    entity: str = Query(..., min_length=1),
    entity_id: str = Query(..., min_length=1),
    step: int = Query(0, ge=0),
) -> HTMLResponse:
    """
    Chronological audit events for one entity instance; each step shows only that event's field deltas.
    """
    entity_clean = entity.strip()
    entity_id_clean = entity_id.strip()
    if not entity_clean or not entity_id_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="entity and entity_id must not be empty",
        )

    rows, truncated = _timeline_rows(
        db,
        entity=entity_clean,
        entity_id=entity_id_clean,
    )
    qs_base = urlencode({"entity": entity_clean, "entity_id": entity_id_clean})

    if not rows:
        return templates.TemplateResponse(
            request=request,
            name="audit_timeline.html",
            context={
                "has_rows": False,
                "entity": entity_clean,
                "entity_id": entity_id_clean,
                "qs_base": qs_base,
                "truncated": truncated,
            },
        )

    step = max(0, min(step, len(rows) - 1))
    current = rows[step]
    payload = _parse_response_payload(current.response)
    changes: dict[str, Any] = {}
    if isinstance(payload, dict):
        raw_ch = payload.get("changes")
        if isinstance(raw_ch, dict):
            changes = raw_ch

    return templates.TemplateResponse(
        request=request,
        name="audit_timeline.html",
        context={
            "has_rows": True,
            "entity": entity_clean,
            "entity_id": entity_id_clean,
            "qs_base": qs_base,
            "truncated": truncated,
            "total": len(rows),
            "step": step,
            "row": current,
            "changes": changes,
            "has_prev": step > 0,
            "has_next": step < len(rows) - 1,
        },
    )


@router.get("/{audit_id}/detail", response_class=HTMLResponse, include_in_schema=False)
def audit_detail_fragment(
    request: Request,
    audit_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    row = db.get(Audit, audit_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")

    formatted = json.dumps(
        _parse_response_payload(row.response),
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    return templates.TemplateResponse(
        request=request,
        name="audit_detail.html",
        context={
            "row": row,
            "formatted": formatted,
        },
    )
