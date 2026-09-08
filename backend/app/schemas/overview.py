"""M8.4 — instrument-scoped Order overview response schemas.

Summary / operational grain only. This is deliberately NOT the M7 detailed
clinical result schema: no result values, units, flags, reference ranges, raw
messages, classification metadata or any editable clinical field. Read-only.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class OrderOverviewRow(BaseModel):
    # One row == one Order (see overview_service).
    id_order: int
    waktu_order: datetime
    status_order: str

    # Patient / visit identity (displayed; the row is still order-grained).
    nomor_rm: str
    nama_lengkap: str
    no_registrasi: str
    id_visit: int

    # The "effective run": M7's first-selected run for this order, restricted to
    # the requested instrument (is_final DESC, run_sequence DESC, id_run DESC).
    # Nullable in the type only; the instrument-scoping condition guarantees at
    # least one matching run, so in practice these are always populated.
    effective_run_id: Optional[int] = None
    effective_run_sequence: Optional[int] = None
    effective_run_waktu_run: Optional[datetime] = None

    is_final: bool
    # Delivery is TestRun-level and only meaningful for a final run. NULL when
    # the order has no final run (which is a normal state, not an error).
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None

    # COUNT of results for the effective run only where flag_abnormalitas IS NOT
    # NULL (never summed across reruns / the whole order).
    abnormal_count: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedOrderOverviewResponse(BaseModel):
    items: List[OrderOverviewRow]
    page: int
    page_size: int
    total: int
