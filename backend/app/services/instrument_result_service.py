"""Read-only queries for XN-550 unlinked instrument results (G2).

Implements docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md
Appendix B. Reads only ``instrument_result_sets``, ``instrument_result_items``,
``instrument_messages``, ``instrument_sessions`` and ``instruments``. It never
reads, joins or imports a clinical, user or audit table, never filters or
searches by ``sample_label``, and never writes anything.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.integration.xn550_normalize import IDENTITY_NOTICE
from app.integration.xn550_observations import delivery_group_conditions
from app.models import (
    Instrument,
    InstrumentMessage,
    InstrumentResultItem,
    InstrumentResultSet,
    InstrumentSession,
)

RAW_SHA256_PREFIX_LENGTH = 12


def _delivery_count_subquery(owner):
    """Correlated count of the owning message's §13.2 delivery group."""
    member = aliased(InstrumentMessage)
    return (
        select(func.count(member.id_message))
        .where(*delivery_group_conditions(member, owner.id_instrument, owner.raw_sha256))
        .correlate(owner)
        .scalar_subquery()
    )


def _summary(result_set: InstrumentResultSet, instrument_name: str, delivery_count: int) -> dict:
    return {
        "id_result_set": result_set.id_result_set,
        "id_instrument": result_set.id_instrument,
        "instrument_name": instrument_name,
        "received_at": result_set.received_at,
        "analysis_at": result_set.analysis_at,
        "sample_label": result_set.sample_label,
        "association_status": result_set.association_status,
        "duplicate_status": result_set.duplicate_status,
        "possible_duplicate_of": result_set.possible_duplicate_of,
        "item_count": result_set.item_count,
        "non_n_flag_item_count": result_set.non_n_flag_item_count,
        "image_reference_count": result_set.image_reference_count,
        "delivery_count": delivery_count,
    }


def list_instrument_result_sets(
    db: Session,
    *,
    received_from: datetime,
    received_to: datetime,
    id_instrument: Optional[int],
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    """Half-open ``[received_from, received_to)`` over the set's ``received_at``.

    Fixed order ``received_at DESC, id_result_set DESC``. No other filter exists.
    """
    filters = [
        InstrumentResultSet.received_at >= received_from,
        InstrumentResultSet.received_at < received_to,
    ]
    if id_instrument is not None:
        filters.append(InstrumentResultSet.id_instrument == id_instrument)

    total = db.scalar(select(func.count(InstrumentResultSet.id_result_set)).where(*filters))

    owner = aliased(InstrumentMessage)
    rows = db.execute(
        select(InstrumentResultSet, Instrument.nama_mesin, _delivery_count_subquery(owner))
        .join(Instrument, Instrument.id_instrument == InstrumentResultSet.id_instrument)
        .join(owner, owner.id_message == InstrumentResultSet.id_message)
        .where(*filters)
        .order_by(InstrumentResultSet.received_at.desc(), InstrumentResultSet.id_result_set.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_summary(result_set, name, count) for result_set, name, count in rows], int(total or 0)


def get_instrument_result_set(db: Session, id_result_set: int) -> Optional[dict]:
    """One set with its items, deliveries, provenance and the identity notice."""
    owner = aliased(InstrumentMessage)
    row = db.execute(
        select(InstrumentResultSet, Instrument.nama_mesin, _delivery_count_subquery(owner), owner, InstrumentSession)
        .join(Instrument, Instrument.id_instrument == InstrumentResultSet.id_instrument)
        .join(owner, owner.id_message == InstrumentResultSet.id_message)
        .join(InstrumentSession, InstrumentSession.id_session == owner.id_session)
        .where(InstrumentResultSet.id_result_set == id_result_set)
    ).one_or_none()
    if row is None:
        return None
    result_set, instrument_name, delivery_count, owner_message, owner_session = row

    items = db.scalars(
        select(InstrumentResultItem)
        .where(InstrumentResultItem.id_result_set == id_result_set)
        .order_by(InstrumentResultItem.source_r_sequence)
    ).all()

    member = aliased(InstrumentMessage)
    deliveries = db.execute(
        select(member, InstrumentSession.opened_at)
        .join(InstrumentSession, InstrumentSession.id_session == member.id_session)
        .where(*delivery_group_conditions(member, owner_message.id_instrument, owner_message.raw_sha256))
        .order_by(member.id_message)
    ).all()

    detail = _summary(result_set, instrument_name, delivery_count)
    detail.update(
        {
            "identity_notice": IDENTITY_NOTICE,
            "items": [
                {
                    "r_sequence": item.source_r_sequence,
                    "test_code": item.test_code,
                    "item_kind": item.item_kind,
                    "value": item.value_raw,
                    "units": item.units_raw,
                    "reference_range": item.reference_range_raw,
                    "abnormal_flag": item.abnormal_flag_raw,
                    "result_status": item.result_status_raw,
                }
                for item in items
            ],
            "deliveries": [
                {
                    "id_message": message.id_message,
                    "received_at": message.received_at,
                    "id_session": message.id_session,
                    "session_opened_at": opened_at,
                    "read_count": message.read_count,
                }
                for message, opened_at in deliveries
            ],
            "provenance": {
                "id_message": owner_message.id_message,
                "parser_key": owner_message.parser_key,
                "parser_version": owner_message.parser_version,
                "raw_sha256_prefix": owner_message.raw_sha256[:RAW_SHA256_PREFIX_LENGTH],
                "raw_length": owner_message.raw_length,
                "ack_policy": owner_session.ack_policy,
            },
        }
    )
    return detail
