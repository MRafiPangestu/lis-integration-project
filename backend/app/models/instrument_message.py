from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class InstrumentMessage(Base):
    __tablename__ = "instrument_messages"

    id_message: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_instrument: Mapped[int] = mapped_column(
        ForeignKey("instruments.id_instrument"), nullable=False
    )
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="Success"
    )
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    received_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    instrument: Mapped[Instrument] = relationship(back_populates="messages")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="message")

