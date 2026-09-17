from __future__ import annotations

from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InstrumentResultItem(Base):
    """One normalised ``R`` record of an unlinked XN-550 observation set
    (G2; ``docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md``
    §10.3, §11.1).

    * ``source_r_sequence`` is the ASTM ``R``-2 result-record sequence within
      one message — never the instrument's on-screen sequence number, and never
      displayed.
    * ``source_offset_start`` / ``source_offset_end`` are message-relative wire
      byte offsets into the owning message's ``raw_bytes``: ``[start, end)``,
      excluding the record's terminating CR.
    * ``*_raw`` columns hold **uninterpreted semantic text** (E1394-escape
      decoded; no trimming, case change, conversion or mapping). They are not
      wire bytes; ``raw_bytes`` stays authoritative.
    * Image references carry no value: an image path can never be stored
      (CHECK constraint).

    Rows are immutable: no code path updates or deletes them.
    """

    __tablename__ = "instrument_result_items"
    __table_args__ = (
        # Its backing index also serves "all items of a set"; no separate index.
        UniqueConstraint(
            "id_result_set", "source_record_index", name="uk_instrument_result_items_set_record"
        ),
        UniqueConstraint(
            "id_result_set", "test_code", name="uk_instrument_result_items_set_test_code"
        ),
        CheckConstraint(
            "item_kind IN ('MEASURED', 'INTERPRETIVE', 'FLAG_ONLY', 'IMAGE_REFERENCE')",
            name="ck_instrument_result_items_item_kind",
        ),
        CheckConstraint(
            "(item_kind IN ('MEASURED', 'INTERPRETIVE') AND value_raw IS NOT NULL) OR "
            "(item_kind IN ('FLAG_ONLY', 'IMAGE_REFERENCE') AND value_raw IS NULL)",
            name="ck_instrument_result_items_value_by_kind",
        ),
    )

    id_item: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_result_set: Mapped[int] = mapped_column(
        ForeignKey(
            "instrument_result_sets.id_result_set",
            name="fk_instrument_result_items_id_result_set",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    source_record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_offset_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_offset_end: Mapped[int] = mapped_column(Integer, nullable=False)
    # ASTM R-2 result-record sequence within the message. Ordering only.
    source_r_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    item_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    test_code: Mapped[str] = mapped_column(String(50), nullable=False)
    test_code_qualifier: Mapped[Optional[str]] = mapped_column(String(10))
    value_raw: Mapped[Optional[str]] = mapped_column(String(50))
    units_raw: Mapped[Optional[str]] = mapped_column(String(20))
    reference_range_raw: Mapped[Optional[str]] = mapped_column(String(100))
    abnormal_flag_raw: Mapped[Optional[str]] = mapped_column(String(10))
    result_status_raw: Mapped[str] = mapped_column(String(5), nullable=False)
