"""XN-550 G2 database operations: per-instrument lock, duplicate lookups, inserts.

Implements docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md
§14.2 (per-instrument serialisation), §13.2 (delivery group, root link, set
ownership), §13.3 (possible duplicates) and §10.2–§10.4 (observation rows).

Every function runs inside the caller's T2 transaction and never commits. None
of them reads or writes a clinical table: identity stays UNRESOLVED, and
``sample_label`` is never used to look anything up.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.integration.astm.assembler import FRAMING_ASTM_CR_RECORDS
from app.integration.parsers.xn550_astm import RULE_ENVELOPE_CONFORMANT
from app.integration.xn550_normalize import (
    DUPLICATE_NONE,
    DUPLICATE_POSSIBLE,
    FINGERPRINT_VERSION,
    IdentityResolution,
    NormalizedResultSet,
)
from app.models import InstrumentMessage, InstrumentResultItem, InstrumentResultSet

PARSE_STATUS_SUCCESS = "Success"

# Fixed XN-550 T2 advisory-lock namespace (contract §14.2): ASCII "X550" read as
# a 32-bit integer. The second lock key is id_instrument, so instruments never
# block each other.
T2_LOCK_NAMESPACE = 0x58353530  # == 1479882032
# Bounded wait for the lock; a timeout is a T2 exception (contract §10.4 step 9).
T2_LOCK_TIMEOUT = "30s"
_LOCK_TIMEOUT_FORMAT = re.compile(r"[1-9][0-9]*(ms|s)")


def lock_instrument(session: Session, id_instrument: int) -> None:
    """Take the transaction-scoped per-instrument advisory lock.

    It covers the rest of the T2 transaction — row re-read, classification,
    duplicate lookups, set and item inserts, commit — and is released by the
    commit or rollback. Callers must never do socket I/O, ACKs, raw capture,
    HTTP/SIMRS calls or retry backoff while holding it.
    """
    if not _LOCK_TIMEOUT_FORMAT.fullmatch(T2_LOCK_TIMEOUT):
        raise ValueError(f"invalid T2 lock timeout {T2_LOCK_TIMEOUT!r}")
    session.execute(text(f"SET LOCAL lock_timeout = '{T2_LOCK_TIMEOUT}'"))
    session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :id_instrument)"),
        {"namespace": T2_LOCK_NAMESPACE, "id_instrument": id_instrument},
    )


def delivery_group_conditions(message, id_instrument: int, raw_sha256: str) -> tuple:
    """The exact §13.2 membership predicate. No time window; sessions play no part."""
    return (
        message.id_instrument == id_instrument,
        message.raw_sha256 == raw_sha256,
        message.framing == FRAMING_ASTM_CR_RECORDS,
        message.parse_status == PARSE_STATUS_SUCCESS,
        message.classification_rule == RULE_ENVELOPE_CONFORMANT,
    )


def byte_identical_root(
    session: Session, id_instrument: int, raw_sha256: str, before_id_message: int
) -> Optional[int]:
    """Lowest ``id_message`` of the delivery group below *before_id_message*.

    A delivery links only to a lower id. If it is itself the lowest id (for
    example, processed late), it keeps no link, and no other row is updated.
    """
    return session.scalar(
        select(func.min(InstrumentMessage.id_message)).where(
            *delivery_group_conditions(InstrumentMessage, id_instrument, raw_sha256),
            InstrumentMessage.id_message < before_id_message,
        )
    )


def group_owns_result_set(session: Session, id_instrument: int, raw_sha256: str) -> bool:
    """True if any member of the delivery group already owns a result set (§10.4 step 5a)."""
    owner = session.scalar(
        select(InstrumentResultSet.id_result_set)
        .join(InstrumentMessage, InstrumentMessage.id_message == InstrumentResultSet.id_message)
        .where(*delivery_group_conditions(InstrumentMessage, id_instrument, raw_sha256))
        .limit(1)
    )
    return owner is not None


def earliest_same_fingerprint(
    session: Session, id_instrument: int, fingerprint_version: int, fingerprint: str
) -> Optional[int]:
    """Lowest ``id_result_set`` with the same instrument, fingerprint version and fingerprint."""
    return session.scalar(
        select(func.min(InstrumentResultSet.id_result_set)).where(
            InstrumentResultSet.id_instrument == id_instrument,
            InstrumentResultSet.fingerprint_version == fingerprint_version,
            InstrumentResultSet.analysis_fingerprint == fingerprint,
        )
    )


def redelivery_note(root_id_message: int) -> str:
    """The only non-token ``error_detail`` form (contract §17)."""
    return f"Redelivery: byte-identical to message {int(root_id_message)}"


def insert_result_set(
    session: Session,
    *,
    message: InstrumentMessage,
    normalized: NormalizedResultSet,
    fingerprint: str,
    possible_duplicate_of: Optional[int],
    identity: IdentityResolution,
) -> InstrumentResultSet:
    """Insert one result set and all its items (flushed, not committed)."""
    result_set = InstrumentResultSet(
        id_message=message.id_message,
        id_instrument=message.id_instrument,
        received_at=message.received_at,
        analysis_at=normalized.analysis_at,
        sample_label=normalized.sample_label,
        association_status=identity.status,
        analysis_fingerprint=fingerprint,
        fingerprint_version=FINGERPRINT_VERSION,
        duplicate_status=DUPLICATE_POSSIBLE if possible_duplicate_of is not None else DUPLICATE_NONE,
        possible_duplicate_of=possible_duplicate_of,
        p5_populated=normalized.p5_populated,
        p8_populated=normalized.p8_populated,
        item_count=normalized.item_count,
        non_n_flag_item_count=normalized.non_n_flag_item_count,
        image_reference_count=normalized.image_reference_count,
    )
    session.add(result_set)
    session.flush()
    session.add_all(
        InstrumentResultItem(
            id_result_set=result_set.id_result_set,
            source_record_index=item.source_record_index,
            source_offset_start=item.source_offset_start,
            source_offset_end=item.source_offset_end,
            source_r_sequence=item.source_r_sequence,
            item_kind=item.item_kind,
            test_code=item.test_code,
            test_code_qualifier=item.test_code_qualifier,
            value_raw=item.value_raw,
            units_raw=item.units_raw,
            reference_range_raw=item.reference_range_raw,
            abnormal_flag_raw=item.abnormal_flag_raw,
            result_status_raw=item.result_status_raw,
        )
        for item in normalized.items
    )
    session.flush()
    return result_set
