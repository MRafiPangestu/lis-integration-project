from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InstrumentSession(Base):
    """One accepted TCP connection from a listener-mode instrument.

    Transport provenance for XN-550 raw capture
    (``docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md`` §9.1).
    A row is opened when an allowed peer is accepted and closed with a
    ``close_reason`` when the connection ends; ``closed_at IS NULL`` means the
    session is (or was, until a crash) open. Contains no PHI.
    """

    __tablename__ = "instrument_sessions"

    id_session: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_instrument: Mapped[int] = mapped_column(
        ForeignKey("instruments.id_instrument"), nullable=False
    )
    transport_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    local_address: Mapped[str] = mapped_column(String(45), nullable=False)
    local_port: Mapped[int] = mapped_column(Integer, nullable=False)
    peer_address: Mapped[str] = mapped_column(String(45), nullable=False)
    peer_port: Mapped[int] = mapped_column(Integer, nullable=False)
    ack_policy: Mapped[str] = mapped_column(String(50), nullable=False)
    opened_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False)
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    # PEER_RESET, PEER_CLOSED, READ_ERROR, SUPERSEDED, LIS_SHUTDOWN,
    # PERSISTENCE_FAILURE, RECOVERED_AT_STARTUP — app-level enum, no CHECK
    # (same convention as connection_status / delivery_status).
    close_reason: Mapped[Optional[str]] = mapped_column(String(30))
    bytes_received: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    reads_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    acks_sent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    messages_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    fragments_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )


Index(
    "idx_instrument_sessions_instrument_opened",
    InstrumentSession.id_instrument,
    InstrumentSession.opened_at.desc(),
)
