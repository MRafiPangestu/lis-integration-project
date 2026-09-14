from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AuditEvent(Base):
    """Append-only workflow / user-management audit trail (M9.1b).

    One row per successfully committed, human-attributed state transition —
    see ``docs/M9.1b_AUDIT_ATTRIBUTION_DESIGN.md`` (OD-B1..OD-B7). This table
    is INSERT-only by **application** discipline (OD-B4): no endpoint updates
    or deletes a row here, and none should ever be added. There is no DB
    trigger or REVOKE enforcing that — OD-B4 explicitly scoped enforcement to
    the application layer for this milestone.

    ``entity_id`` is deliberately **not** a foreign key: a single table
    records actions against more than one entity kind (``entity_type``
    distinguishes them — currently ``"TEST_RUN"`` or ``"USER"``), and one
    integer column cannot reference two different parent tables. Referential
    integrity for ``entity_id`` is an application concern — safe in practice
    because every audit insert happens in the same transaction as the
    mutation that creates or touches the referenced row, and because neither
    ``TestRun`` nor ``User`` rows are ever deleted (users are deactivated via
    ``is_active``, never removed).

    ``id_user`` **is** a real foreign key (to ``users.id_user``, ON DELETE
    RESTRICT). Every row M9.1b itself ever writes has a concrete authenticated
    actor — login, reads, and instrument ingestion are all out of scope (see
    the design doc §5) — so ``id_user`` is never actually NULL in practice
    today. It is nullable in the schema because a system-originated event is
    conceptually possible in the future, and RESTRICT exists to make explicit
    a guarantee that already holds implicitly: the application never deletes
    a ``User`` row, so this constraint should never actually fire.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        # Entity history: "show me everything that happened to this TestRun / User."
        Index("idx_audit_events_entity", "entity_type", "entity_id", "occurred_at"),
        # Actor history: "show me everything this person did."
        Index("idx_audit_events_actor", "id_user", "occurred_at"),
    )

    id_audit: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_user: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id_user", ondelete="RESTRICT"), nullable=True
    )
    actor_username: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )
    # OD-B3: M9.1b records successful, committed transitions only — every row
    # this milestone writes has outcome "SUCCESS". The column exists (per the
    # target model) for forward extensibility without a schema change; no
    # code path in M9.1b writes any other value.
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    # Short, human-readable state labels (e.g. "NOT_FINAL"/"FINAL",
    # "pending"/"sending") — not JSON, per the target model. Never populated
    # with credential material (see PASSWORD_CHANGED handling).
    state_before: Mapped[Optional[str]] = mapped_column(String(30))
    state_after: Mapped[Optional[str]] = mapped_column(String(30))
