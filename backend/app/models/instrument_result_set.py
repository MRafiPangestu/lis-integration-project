from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class InstrumentResultSet(Base):
    """One **unlinked** XN-550 observation set: the normalised results of one
    envelope-conformant delivery (G2;
    ``docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md`` §10.2).

    Identity boundary (contract §12.3):

    * ``sample_label`` is the instrument's Sample No. as typed by the operator.
      It is a **display label only** — never a patient, specimen, visit or
      order key — and is deliberately not indexed, unique, filtered or sorted.
    * ``association_status`` (the identity status) is always ``UNRESOLVED``
      under this contract; a CHECK constraint enforces it.
    * There is no foreign key to any clinical table (patients, visits, orders,
      test runs, results): these rows are never associated with a patient or
      specimen.

    Duplicate handling (contract §13): ``duplicate_status`` is a flag only and
    never suppresses a set; ``possible_duplicate_of`` points to the lowest-id
    set with the same instrument, fingerprint version and fingerprint.

    Rows are immutable: no code path updates or deletes them.
    """

    __tablename__ = "instrument_result_sets"
    __table_args__ = (
        UniqueConstraint("id_message", name="uk_instrument_result_sets_id_message"),
        CheckConstraint(
            "association_status = 'UNRESOLVED'",
            name="ck_instrument_result_sets_association_status",
        ),
        CheckConstraint(
            "(duplicate_status = 'NONE' AND possible_duplicate_of IS NULL) OR "
            "(duplicate_status = 'POSSIBLE_DUPLICATE' AND possible_duplicate_of IS NOT NULL "
            "AND possible_duplicate_of < id_result_set)",
            name="ck_instrument_result_sets_duplicate_state",
        ),
        # §13.3 lookup of the lowest-id set with the same fingerprint.
        Index(
            "idx_instrument_result_sets_fingerprint",
            "id_instrument",
            "fingerprint_version",
            "analysis_fingerprint",
            "id_result_set",
        ),
    )

    id_result_set: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_message: Mapped[int] = mapped_column(
        ForeignKey(
            "instrument_messages.id_message",
            name="fk_instrument_result_sets_id_message_instrument_messages",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    id_instrument: Mapped[int] = mapped_column(
        ForeignKey(
            "instruments.id_instrument",
            name="fk_instrument_result_sets_id_instrument_instruments",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    # LIS clock: copy of the owning message's received_at (list filter and sort key).
    received_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False)
    # Instrument clock: R-13 analysis time, never corrected.
    analysis_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False)
    # O-4 component 3 — DISPLAY LABEL ONLY (PHI). Never an identifier.
    sample_label: Mapped[str] = mapped_column(String(100), nullable=False)
    # Identity status. Always UNRESOLVED under this contract.
    association_status: Mapped[str] = mapped_column(String(20), nullable=False)
    analysis_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    fingerprint_version: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_status: Mapped[str] = mapped_column(String(20), nullable=False)
    possible_duplicate_of: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "instrument_result_sets.id_result_set",
            name="fk_instrument_result_sets_possible_duplicate_of",
            ondelete="RESTRICT",
        )
    )
    # Presence of P-5 / P-8 only. Internal storage metadata: never exposed.
    p5_populated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    p8_populated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Lexical: items whose flag is present and not exactly "N". Not "abnormal".
    non_n_flag_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    image_reference_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.current_timestamp()
    )


Index(
    "idx_instrument_result_sets_received",
    InstrumentResultSet.received_at.desc(),
    InstrumentResultSet.id_result_set.desc(),
)
Index(
    "idx_instrument_result_sets_instrument_received",
    InstrumentResultSet.id_instrument,
    InstrumentResultSet.received_at.desc(),
    InstrumentResultSet.id_result_set.desc(),
)
