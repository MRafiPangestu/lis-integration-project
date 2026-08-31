from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        # Prevent duplicate run_sequence within the same order
        UniqueConstraint("id_order", "run_sequence", name="uk_order_run_sequence"),
        # At most one final run per order (PostgreSQL partial unique index)
        Index(
            "idx_unique_final_run_per_order",
            "id_order",
            unique=True,
            postgresql_where=text("is_final = TRUE"),
        ),
    )

    id_run: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_order: Mapped[int] = mapped_column(ForeignKey("orders.id_order"), nullable=False)
    id_instrument: Mapped[int] = mapped_column(
        ForeignKey("instruments.id_instrument"), nullable=False
    )
    id_message: Mapped[Optional[int]] = mapped_column(
        ForeignKey("instrument_messages.id_message")
    )
    run_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    waktu_run: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    is_final: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    delivery_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending"
    )
    delivered_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    order: Mapped[Order] = relationship(back_populates="test_runs")
    instrument: Mapped[Instrument] = relationship(back_populates="test_runs")
    message: Mapped[Optional[InstrumentMessage]] = relationship(back_populates="test_runs")
    results: Mapped[list[Result]] = relationship(back_populates="test_run")

