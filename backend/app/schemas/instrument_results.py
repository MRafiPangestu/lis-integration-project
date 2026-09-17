"""XN-550 unlinked instrument results — read-only response schemas (G2).

Mirrors docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md Appendix
B exactly; mirrored in ``frontend/src/types/api.ts``. Every class derives
directly from ``BaseModel``: no clinical schema is imported or extended.

Identity boundary: ``sample_label`` is a display label only; ``association_status``
is always ``UNRESOLVED``; ``r_sequence`` is the ASTM ``R``-2 result-record
sequence (ordering only, never displayed). Never exposed: raw bytes or raw
message text, the full SHA-256, the fingerprint, ``P``-5 / ``P``-8 values or
presence flags, image paths, ``H``-5, ``R``-11, network endpoints, and any
clinical, audit or user data.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class InstrumentResultSetSummary(BaseModel):
    id_result_set: int
    id_instrument: int
    instrument_name: str
    received_at: datetime  # LIS clock
    analysis_at: datetime  # instrument clock
    sample_label: str  # display label only
    association_status: str  # always UNRESOLVED
    duplicate_status: str  # NONE | POSSIBLE_DUPLICATE
    possible_duplicate_of: Optional[int] = None
    item_count: int
    non_n_flag_item_count: int  # lexical count; never "abnormal"
    image_reference_count: int
    delivery_count: int  # §13.2 delivery-group size, query-derived


class PaginatedInstrumentResultSetResponse(BaseModel):
    items: List[InstrumentResultSetSummary]
    page: int
    page_size: int
    total: int
    identity_notice: str


class InstrumentResultItemResponse(BaseModel):
    r_sequence: int  # ASTM R-2 result-record sequence; ordering only
    test_code: str
    item_kind: str
    value: Optional[str] = None
    units: Optional[str] = None
    reference_range: Optional[str] = None
    abnormal_flag: Optional[str] = None  # verbatim; no mapping
    result_status: str


class InstrumentResultDeliveryResponse(BaseModel):
    id_message: int
    received_at: datetime
    id_session: int
    session_opened_at: datetime
    read_count: int


class InstrumentResultProvenanceResponse(BaseModel):
    id_message: int
    parser_key: str
    parser_version: str
    raw_sha256_prefix: str  # first 12 lowercase hex characters only
    raw_length: int
    ack_policy: str


class InstrumentResultSetDetail(BaseModel):
    id_result_set: int
    id_instrument: int
    instrument_name: str
    received_at: datetime
    analysis_at: datetime
    sample_label: str
    association_status: str
    duplicate_status: str
    possible_duplicate_of: Optional[int] = None
    item_count: int
    non_n_flag_item_count: int
    image_reference_count: int
    delivery_count: int
    identity_notice: str
    items: List[InstrumentResultItemResponse]
    deliveries: List[InstrumentResultDeliveryResponse]
    provenance: InstrumentResultProvenanceResponse
