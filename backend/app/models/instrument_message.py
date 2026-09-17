from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class InstrumentMessage(Base):
    __tablename__ = "instrument_messages"
    __table_args__ = (
        # XN-550 raw capture (contract §9.2). One byte offset starts at most one
        # message or fragment per session. NULL for MLLP/BC-5150 rows, which
        # PostgreSQL treats as distinct.
        UniqueConstraint(
            "id_session", "stream_offset_start", name="uk_instrument_messages_session_offset"
        ),
        CheckConstraint(
            "raw_bytes IS NULL OR raw_length = octet_length(raw_bytes)",
            name="ck_instrument_messages_raw_length",
        ),
        CheckConstraint(
            "raw_bytes IS NULL OR raw_sha256 IS NOT NULL",
            name="ck_instrument_messages_raw_sha256",
        ),
        # Byte-identity lookup. Deliberately NOT unique: a same-day manual
        # retransmission is byte-identical and every delivery is kept.
        Index("idx_instrument_messages_instrument_sha256", "id_instrument", "raw_sha256"),
        Index("idx_instrument_messages_duplicate_of", "duplicate_of_message_id"),
    )

    id_message: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_instrument: Mapped[int] = mapped_column(
        ForeignKey("instruments.id_instrument"), nullable=False
    )
    # For XN-550 raw capture this is a non-authoritative ASCII rendering of
    # raw_bytes (compatibility / investigation only); raw_bytes is authoritative.
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="Success"
    )
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    # M8.2 classification axis (separate from parse_status). NULL means the row
    # was ingested before M8.2 existed, or — for XN-550 Phase 1 raw capture — a
    # complete message still `Pending` because no T2 stage exists yet.
    message_class: Mapped[Optional[str]] = mapped_column(String(32))
    classification_rule: Mapped[Optional[str]] = mapped_column(String(100))
    received_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )

    # --- XN-550 raw capture provenance (contract §9.2). All nullable; every
    # MLLP/BC-5150 code path leaves them NULL. ---------------------------------
    id_session: Mapped[Optional[int]] = mapped_column(
        ForeignKey("instrument_sessions.id_session")
    )
    session_message_index: Mapped[Optional[int]] = mapped_column(Integer)
    stream_offset_start: Mapped[Optional[int]] = mapped_column(BigInteger)
    stream_offset_end: Mapped[Optional[int]] = mapped_column(BigInteger)
    raw_bytes: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    raw_sha256: Mapped[Optional[str]] = mapped_column(CHAR(64))
    raw_length: Mapped[Optional[int]] = mapped_column(Integer)
    first_byte_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    read_count: Mapped[Optional[int]] = mapped_column(Integer)
    framing: Mapped[Optional[str]] = mapped_column(String(30))
    parser_key: Mapped[Optional[str]] = mapped_column(String(50))
    parser_version: Mapped[Optional[str]] = mapped_column(String(30))
    duplicate_of_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("instrument_messages.id_message")
    )

    # Relationships
    instrument: Mapped[Instrument] = relationship(back_populates="messages")
    test_runs: Mapped[list[TestRun]] = relationship(back_populates="message")


Index(
    "idx_instrument_messages_instrument_received",
    InstrumentMessage.id_instrument,
    InstrumentMessage.received_at.desc(),
)
