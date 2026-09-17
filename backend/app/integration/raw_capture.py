"""T1 raw-capture persistence for listener-mode instruments (XN-550 Phase 1).

Implements docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md §9.3
for G1 ``raw_only``:

* one ``instrument_sessions`` row per accepted connection;
* one ``instrument_messages`` row per complete message **or** fragment, each
  committed in its own transaction, carrying the exact received bytes, their
  SHA-256 and transport provenance.

Nothing here parses field content, classifies clinical data, detects
duplicates or touches Patient / Visit / Order / TestRun / Result. A complete
message without a byte-class problem is stored ``parse_status = 'Pending'``
with ``message_class``, ``parser_key``, ``parser_version`` and
``duplicate_of_message_id`` left NULL: no T2 stage exists in Phase 1
(contract §19.4). Conditions the assembler itself detects — fragments and
§5.3 byte classes — are terminal at T1 as ``UNPARSEABLE`` with their contract
token; that is a statement about bytes, not about clinical content.

No PHI is logged by this module.
"""
from __future__ import annotations

import datetime
import hashlib
import logging
from dataclasses import dataclass
from typing import Callable, Protocol

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.integration.astm.assembler import (
    FRAMING_ASTM_CR_RECORDS,
    AssemblerEvent,
    CompleteMessage,
    Fragment,
)
from app.integration.classification import MessageClass
from app.models import InstrumentMessage, InstrumentSession

log = logging.getLogger(__name__)

PARSE_STATUS_PENDING = "Pending"
PARSE_STATUS_FAILED = "Failed"

TRANSPORT_MODE_LISTENER = "listener"

# close_reason domain (contract §4.4).
CLOSE_PEER_RESET = "PEER_RESET"
CLOSE_PEER_CLOSED = "PEER_CLOSED"
CLOSE_READ_ERROR = "READ_ERROR"
CLOSE_SUPERSEDED = "SUPERSEDED"
CLOSE_LIS_SHUTDOWN = "LIS_SHUTDOWN"
CLOSE_PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
CLOSE_RECOVERED_AT_STARTUP = "RECOVERED_AT_STARTUP"


@dataclass(frozen=True)
class SessionContext:
    id_instrument: int
    transport_mode: str
    local_address: str
    local_port: int
    peer_address: str
    peer_port: int
    ack_policy: str
    opened_at: datetime.datetime


@dataclass
class SessionCounters:
    bytes_received: int = 0
    reads_count: int = 0
    acks_sent: int = 0
    messages_completed: int = 0
    fragments_count: int = 0


class RawCaptureStore(Protocol):
    """Persistence boundary used by the listener (Appendix A: SessionStore + RawMessageStore)."""

    def open_session(self, ctx: SessionContext) -> int: ...

    def close_session(
        self,
        id_session: int,
        reason: str,
        counters: SessionCounters,
        closed_at: datetime.datetime,
    ) -> None: ...

    def close_orphan_sessions(self, id_instrument: int, closed_at: datetime.datetime) -> int: ...

    def persist_event(
        self,
        id_instrument: int,
        id_session: int,
        session_message_index: int,
        event: AssemblerEvent,
    ) -> int: ...

    def health_check(self) -> bool: ...


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def display_text(raw: bytes) -> str:
    """Non-authoritative ASCII rendering for the legacy ``raw_message`` column.

    Undecodable bytes become U+FFFD. NUL is also replaced, because PostgreSQL
    TEXT cannot store it; ``raw_bytes`` keeps every byte exactly.
    """
    return raw.decode("ascii", errors="replace").replace("\x00", "�")


def build_message_row(
    id_instrument: int,
    id_session: int,
    session_message_index: int,
    event: AssemblerEvent,
) -> InstrumentMessage:
    """Map one assembler event to its T1 ``instrument_messages`` row (not yet added to a session)."""
    raw = event.raw
    row = InstrumentMessage(
        id_instrument=id_instrument,
        raw_message=display_text(raw),
        received_at=event.last_byte_at,
        id_session=id_session,
        session_message_index=session_message_index,
        stream_offset_start=event.offset_start,
        stream_offset_end=event.offset_end,
        raw_bytes=raw,
        raw_sha256=sha256_hex(raw),
        raw_length=len(raw),
        first_byte_at=event.first_byte_at,
        read_count=event.read_count,
        framing=FRAMING_ASTM_CR_RECORDS,
        parser_key=None,
        parser_version=None,
        duplicate_of_message_id=None,
    )
    if isinstance(event, Fragment):
        token = event.reason
    elif isinstance(event, CompleteMessage):
        token = event.byte_class_token
    else:  # pragma: no cover - defensive
        raise TypeError(f"unsupported assembler event {type(event).__name__}")

    if token is None:
        row.parse_status = PARSE_STATUS_PENDING
    else:
        row.parse_status = PARSE_STATUS_FAILED
        row.message_class = MessageClass.UNPARSEABLE.value
        row.classification_rule = token
        row.error_detail = token
    return row


class SqlRawCaptureStore:
    """SQLAlchemy implementation. Every call uses its own short-lived Session and commit."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def open_session(self, ctx: SessionContext) -> int:
        with self._session_factory() as session:
            row = InstrumentSession(
                id_instrument=ctx.id_instrument,
                transport_mode=ctx.transport_mode,
                local_address=ctx.local_address,
                local_port=ctx.local_port,
                peer_address=ctx.peer_address,
                peer_port=ctx.peer_port,
                ack_policy=ctx.ack_policy,
                opened_at=ctx.opened_at,
            )
            session.add(row)
            session.commit()
            return row.id_session

    def close_session(
        self,
        id_session: int,
        reason: str,
        counters: SessionCounters,
        closed_at: datetime.datetime,
    ) -> None:
        with self._session_factory() as session:
            session.execute(
                update(InstrumentSession)
                .where(InstrumentSession.id_session == id_session)
                .values(
                    closed_at=closed_at,
                    close_reason=reason,
                    bytes_received=counters.bytes_received,
                    reads_count=counters.reads_count,
                    acks_sent=counters.acks_sent,
                    messages_completed=counters.messages_completed,
                    fragments_count=counters.fragments_count,
                )
            )
            session.commit()

    def close_orphan_sessions(self, id_instrument: int, closed_at: datetime.datetime) -> int:
        """Close rows left open by a previous process (RR-9). Their true end time is unknown."""
        with self._session_factory() as session:
            ids = session.scalars(
                select(InstrumentSession.id_session).where(
                    InstrumentSession.id_instrument == id_instrument,
                    InstrumentSession.closed_at.is_(None),
                )
            ).all()
            if ids:
                session.execute(
                    update(InstrumentSession)
                    .where(InstrumentSession.id_session.in_(ids))
                    .values(closed_at=closed_at, close_reason=CLOSE_RECOVERED_AT_STARTUP)
                )
                session.commit()
            return len(ids)

    def persist_event(
        self,
        id_instrument: int,
        id_session: int,
        session_message_index: int,
        event: AssemblerEvent,
    ) -> int:
        with self._session_factory() as session:
            row = build_message_row(id_instrument, id_session, session_message_index, event)
            session.add(row)
            session.commit()
            return row.id_message

    def health_check(self) -> bool:
        try:
            with self._session_factory() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            log.warning("raw capture store health check failed", exc_info=False)
            return False
