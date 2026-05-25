"""Integration tests for entity audit session listeners (PostgreSQL + Testcontainers)."""

from __future__ import annotations

import json
from ipaddress import IPv4Address

import pytest
from sqlalchemy import func, select, update

from fastapi_audit.services.audit.request_context import (
    AUDIT_SESSION_INFO_KEY,
    AuditRequestContext,
    FALLBACK_CHANGED_BY,
)
from fastapi_audit.services.audit.sanitize import hash_value

pytestmark = pytest.mark.integration


def _audit_by_method(session, method: str):
    """Get audit rows by method."""
    from fastapi_audit.models.audit.orm import Audit

    return list(session.scalars(select(Audit).where(Audit.method == method)))


def _audit_count(session) -> int:
    """Get audit count."""
    from fastapi_audit.models.audit.orm import Audit

    return session.scalar(select(func.count()).select_from(Audit)) or 0


def create_user(db_session, User_model, **kwargs):
    user = User_model(**kwargs)
    db_session.add(user)
    db_session.commit()
    return user


class TestInsertAuditFlow:
    """Persisted ``Audit`` row shape after INSERT flush/commit."""

    def test_writes_audit_row_with_url_and_sanitized_changes(
        self, db_session, User_model
    ):
        """Test writes audit row with url and sanitized changes."""
        user = create_user(
            db_session,
            User_model,
            email="alice@example.com",
            name="Alice",
            phone="5551234567",
        )

        rows = _audit_by_method(db_session, "INSERT")
        assert len(rows) == 1
        assert rows[0].url == f"/entity/User/{user.id}"

        payload = json.loads(rows[0].response)
        assert payload["entity"] == "User"
        assert payload["entity_id"] == user.id
        changes = payload["changes"]
        assert "id" not in changes
        assert changes["email"] == {"new": "a***@example.com"}
        assert changes["name"] == {"new": "Alice"}
        assert changes["phone"] == {"new": "***4567"}

    def test_rollback_after_flush_discards_pending_audit(self, db_session, User_model):
        """Test rollback after flush discards pending audit."""
        user = User_model(email="rb@example.com", name="Rb", phone=None)
        db_session.add(user)
        db_session.flush()

        assert len(_audit_by_method(db_session, "INSERT")) == 1

        db_session.rollback()
        db_session.expire_all()

        assert db_session.scalar(select(func.count()).select_from(User_model)) == 0
        assert _audit_count(db_session) == 0


class TestUpdateAuditFlow:
    """ORM attribute updates vs listener behaviour."""

    def test_tracks_old_and_new_when_value_changes(self, db_session, User_model):
        """Test tracks old and new when value changes."""
        user = create_user(
            db_session,
            User_model,
            email="u@example.com",
            name="Before",
            phone=None,
        )

        db_session.refresh(user)
        user.name = "After"
        db_session.commit()

        rows = _audit_by_method(db_session, "UPDATE")
        assert len(rows) == 1
        payload = json.loads(rows[0].response)
        assert payload["entity_id"] == user.id
        assert payload["changes"]["name"]["old"] == "Before"
        assert payload["changes"]["name"]["new"] == "After"

    def test_no_audit_when_assigning_attribute_to_same_value(
        self, db_session, User_model
    ):
        """Test no audit when assigning attribute to same value."""
        user = create_user(
            db_session,
            User_model,
            email="noop@example.com",
            name="Stable",
            phone=None,
        )

        db_session.refresh(user)
        user.name = user.name
        user.email = user.email
        user.phone = user.phone
        db_session.commit()

        assert not _audit_by_method(db_session, "UPDATE")
        assert user.name == "Stable"
        assert user.email == "noop@example.com"
        assert user.phone is None

    def test_core_update_statement_does_not_emit_orm_update_audit(
        self, db_session, User_model
    ):
        """Test core update statement does not emit ORM update audit."""
        user = create_user(
            db_session,
            User_model,
            email="bulk@example.com",
            name="Original",
            phone=None,
        )

        db_session.execute(
            update(User_model)
            .where(User_model.id == user.id)
            .values(name="BulkChanged")
        )
        db_session.commit()

        db_session.refresh(user)
        assert user.name == "BulkChanged"
        assert not _audit_by_method(db_session, "UPDATE")


class TestDeleteAuditFlow:
    """DELETE snapshots, path fallbacks, and prior-row rewrite."""

    def test_delete_snapshot_uses_on_delete_strategies(self, db_session, User_model):
        """Test delete snapshot uses on delete strategies."""
        user = create_user(
            db_session,
            User_model,
            email="d@example.com",
            name="SecretName",
            phone="9998887777",
        )
        db_session.delete(user)
        db_session.commit()

        rows = _audit_by_method(db_session, "DELETE")
        assert len(rows) == 1
        payload = json.loads(rows[0].response)
        changes = payload["changes"]
        assert "id" not in changes
        assert "email" not in changes
        assert changes["name"]["old"] == hash_value("SecretName")
        assert changes["name"]["new"] is None
        assert changes["phone"]["old"] == hash_value("9998887777")
        assert changes["phone"]["new"] is None

    def test_delete_without_entity_id_uses_safe_path_and_payload(
        self, db_session, User_model, monkeypatch
    ):
        """Test delete without entity id uses safe path and payload."""
        from fastapi_audit.models.audit import session_listeners as sl

        user = create_user(
            db_session,
            User_model,
            email="nopk@example.com",
            name="Nopk",
            phone=None,
        )
        real_pk = sl.primary_key_value

        def primary_key_value_patched(obj):
            if obj is user:
                return None
            return real_pk(obj)

        monkeypatch.setattr(sl, "primary_key_value", primary_key_value_patched)

        db_session.delete(user)
        db_session.commit()

        rows = _audit_by_method(db_session, "DELETE")
        assert len(rows) == 1
        assert rows[0].url == "/entity/User"
        payload = json.loads(rows[0].response)
        assert payload.get("entity_id") is None

    def test_prior_update_payloads_resanitized_after_delete(
        self, db_session, User_model
    ):
        """Test prior update payloads resanitized after delete."""
        user = create_user(
            db_session,
            User_model,
            email="a@b.c",
            name="N1",
            phone=None,
        )

        db_session.refresh(user)
        user.email = "z@y.x"
        user.name = "N2"
        db_session.commit()

        update_rows = _audit_by_method(db_session, "UPDATE")
        assert len(update_rows) == 1
        before = json.loads(update_rows[0].response)["changes"]
        assert "email" in before
        assert before["name"]["old"] == "N1"
        assert before["name"]["new"] == "N2"

        db_session.delete(user)
        db_session.commit()

        from fastapi_audit.models.audit.orm import Audit

        db_session.expire_all()
        upd = db_session.scalars(select(Audit).where(Audit.method == "UPDATE")).one()
        after = json.loads(upd.response)["changes"]
        assert "email" not in after
        assert after["name"]["old"] == hash_value("N1")
        assert after["name"]["new"] == hash_value("N2")


class TestContextResolution:
    """``AuditRequestContext`` on ``session.info`` vs defaults."""

    def test_audit_row_uses_session_request_context(self, db_session, User_model):
        """Test audit row uses session request context."""
        db_session.info[AUDIT_SESSION_INFO_KEY] = AuditRequestContext(
            changed_by="actor-99",
            ip_address=IPv4Address("203.0.113.10"),
        )
        create_user(
            db_session,
            User_model,
            email="ctx@example.com",
            name="Ctx",
            phone=None,
        )

        row = _audit_by_method(db_session, "INSERT")[0]
        assert row.changed_by == "actor-99"
        assert row.ip_address == "203.0.113.10"

    def test_fallback_changed_by_without_context(self, db_session, User_model):
        """Test fallback changed by without context."""
        create_user(
            db_session,
            User_model,
            email="fb@example.com",
            name="Fb",
            phone=None,
        )

        row = _audit_by_method(db_session, "INSERT")[0]
        assert row.changed_by == FALLBACK_CHANGED_BY
        assert row.ip_address == ""


class TestSanitizationRules:
    """Explicit checks that persisted ``changes`` match ``@audited`` strategies."""

    def test_insert_masks_hash_and_typed_mask_per_config(
        self, db_session, User_model
    ):
        """Test insert applies mask:type=email and mask:type=phone per config."""
        user = create_user(
            db_session,
            User_model,
            email="san@example.com",
            name="Plain",
            phone="1002003004",
        )
        payload = json.loads(_audit_by_method(db_session, "INSERT")[0].response)
        ch = payload["changes"]
        assert "id" not in ch
        assert ch["email"] == {"new": "s***@example.com"}
        assert ch["name"] == {"new": "Plain"}
        assert ch["phone"] == {"new": "***3004"}

    def test_delete_hashes_sensitive_fields_per_on_delete_config(
        self, db_session, User_model
    ):
        """Test delete hashes sensitive fields per on delete config."""
        user = create_user(
            db_session,
            User_model,
            email="del@example.com",
            name="ToHash",
            phone="1112223333",
        )
        db_session.delete(user)
        db_session.commit()

        ch = json.loads(_audit_by_method(db_session, "DELETE")[0].response)["changes"]
        assert "email" not in ch
        assert ch["name"]["old"] == hash_value("ToHash")
        assert ch["phone"]["old"] == hash_value("1112223333")
