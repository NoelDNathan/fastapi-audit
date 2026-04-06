import json
from typing import Any, Dict
from sqlalchemy import cast, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models.audit.change_set import (
    any_on_delete_strategy_differs,
    changes_for_delete,
    changes_for_insert,
    changes_for_update,
    resanitize_changes_for_delete,
)
from app.models.audit.orm import Audit, AuditBase
from app.services.audit.request_context import (
    AUDIT_SESSION_INFO_KEY,
    FALLBACK_CHANGED_BY,
    AuditRequestContext,
)

PENDING_ENTITY_AUDIT_KEY = "_pending_entity_audit_rows"

from enum import Enum

class AuditAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"

def is_auditable(obj) -> bool:
    """
    Check if the given object is auditable.
    """
    return isinstance(obj, AuditBase)

def primary_key_value(obj) -> object | None:
    """
    Get the primary key value for the given object.
    """
    inst = sa_inspect(obj)
    ident = inst.identity
    if ident is not None and any(x is not None for x in ident):
        return ident[0] if len(ident) == 1 else ident
    mapper = inst.mapper
    values = []
    for col in mapper.primary_key:
        prop = mapper.get_property_by_column(col)
        values.append(getattr(obj, prop.key, None))
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return tuple(values) if any(v is not None for v in values) else None


def queue_entity_audit(
    session: Session,
    *,
    action: AuditAction,
    obj: AuditBase,
    changes: Dict[str, Any],
) -> None:
    """
    Queue an entity audit entry.
    """
    pending = session.info.setdefault(PENDING_ENTITY_AUDIT_KEY, [])
    entry: dict = {
        "action": action.value,
        "entity": obj.__class__.__name__,
        "changes": changes,
    }
    if action == AuditAction.INSERT:
        entry["_insert_obj"] = obj
    else:
        entry["entity_id"] = primary_key_value(obj)
    if action == AuditAction.DELETE:
        entry["model_cls"] = obj.__class__
    pending.append(entry)


def rewrite_prior_audit_rows(
    session: Session,
    model_cls,
    entity: str,
    entity_id: object,
) -> None:
    """Rewrite prior audit JSON payloads when delete-time sanitization differs from persist."""
    on_delete = getattr(model_cls, "__audit_config_on_delete__", None) or {}
    if not on_delete:
        return
    if not any_on_delete_strategy_differs(model_cls):
        return
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    jb = cast(Audit.response, JSONB)
    stmt = select(Audit).where(
        jb["entity"].astext == entity,
        jb["entity_id"].astext == str(entity_id),
    )
    for row in session.scalars(stmt):
        try:
            data = json.loads(row.response)
        except json.JSONDecodeError:
            continue
        ch = data.get("changes")
        if not isinstance(ch, dict):
            continue
        data["changes"] = resanitize_changes_for_delete(ch, model_cls)
        row.response = json.dumps(data, default=str)


@event.listens_for(Session, "before_flush")
def audit_before_flush(session, flush_context, instances):
    """Queue entity-level audit entries before flush."""
    for obj in session.new:
        if not is_auditable(obj):
            continue
        queue_entity_audit(session, action=AuditAction.INSERT, obj=obj, changes=changes_for_insert(obj))

    for obj in session.dirty:
        if not is_auditable(obj):
            continue
        ch = changes_for_update(obj)
        if ch:
            queue_entity_audit(session, action=AuditAction.UPDATE, obj=obj, changes=ch)

    for obj in session.deleted:
        if not is_auditable(obj):
            continue
        queue_entity_audit(session, action=AuditAction.DELETE, obj=obj, changes=changes_for_delete(obj))


@event.listens_for(Session, "after_flush_postexec")
def audit_after_flush_postexec(session, flush_context):
    """
    Persist audit rows after flush postexec so new instances have PKs populated
    (identity is not always set in after_flush).
    """
    pending = session.info.pop(PENDING_ENTITY_AUDIT_KEY, None)
    if not pending:
        return
    for item in pending:
        action = AuditAction(item["action"])
        entity = item["entity"]
        changes = item["changes"]
        insert_obj = item.get("_insert_obj")
        if insert_obj is not None:
            eid = primary_key_value(insert_obj)
        else:
            eid = item.get("entity_id")

        if action == AuditAction.DELETE and eid is not None:
            model_cls = item.get("model_cls")
            if model_cls is not None:
                rewrite_prior_audit_rows(session, model_cls, entity, eid)

        # TODO: !!! Separar en un service aparte?
        path = f"/entity/{entity}/{eid}" if eid is not None else f"/entity/{entity}"
        payload = json.dumps(
            {"entity": entity, "entity_id": eid, "changes": changes},
            default=str,
        )
        raw_ctx = session.info.get(AUDIT_SESSION_INFO_KEY)
        if isinstance(raw_ctx, AuditRequestContext):
            changed_by = raw_ctx.changed_by
            ip_address = (
                str(raw_ctx.ip_address) if raw_ctx.ip_address is not None else ""
            )
        else:
            changed_by = FALLBACK_CHANGED_BY
            ip_address = ""
        session.add(
            Audit(
                url=path,
                headers=[],
                method=action.value,
                response=payload,
                changed_by=changed_by,
                ip_address=ip_address,
            )
        )
