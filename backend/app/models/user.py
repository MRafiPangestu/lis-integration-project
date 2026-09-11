from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Boolean, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class User(Base):
    """Application account for API authentication (M9.1a).

    This is Workflow Metadata, not Clinical Data (``04_DATABASE_DESIGN.md``
    §25/§26) — it does not make the LIS a patient-identity source of truth.

    ``role`` is validated in the application (``app.core.security.Role``), not
    a DB CHECK constraint, following the schema's existing convention: there
    are zero CHECK constraints today, and ``delivery_status`` /
    ``connection_status`` are the same "app-level enum stored as VARCHAR"
    pattern (design doc §8.2).

    Actor attribution for workflow mutations (``id_user`` on ``test_runs`` /
    an audit trail) is M9.1b — deliberately not implemented here.
    """

    __tablename__ = "users"

    id_user: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nama_lengkap: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )
    last_login_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
