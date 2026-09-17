"""XN-550 unlinked instrument results — read-only API (G2).

docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md Appendix B.
Mounted under ``api_router`` so the deny-by-default ``get_current_user``
dependency applies. Every authenticated user may read (OD-XN-3.1). GET only:
no link, finalise, deliver, retransmit or sync action exists, and there is no
Sample No., patient, MRN or name search.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.integration.xn550_normalize import IDENTITY_NOTICE
from app.schemas.instrument_results import (
    InstrumentResultSetDetail,
    PaginatedInstrumentResultSetResponse,
)
from app.services.instrument_result_service import (
    get_instrument_result_set,
    list_instrument_result_sets,
)

router = APIRouter(prefix="/instrument-results", tags=["instrument-results"])


@router.get("", response_model=PaginatedInstrumentResultSetResponse)
def list_instrument_results(
    received_from: datetime = Query(
        ...,
        description=(
            "Inclusive lower bound on the set's received_at (LIS clock). Server-local "
            "naive datetime; a value with a UTC offset is rejected."
        ),
    ),
    received_to: datetime = Query(
        ...,
        description="Exclusive upper bound on received_at (server-local naive datetime).",
    ),
    id_instrument: Optional[int] = Query(None, description="Exact instrument filter."),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Unlinked XN-550 result sets, newest first. Read-only; identity UNRESOLVED."""
    if received_from.tzinfo is not None or received_to.tzinfo is not None:
        raise HTTPException(
            status_code=422,
            detail="received_from and received_to must be server-local naive datetimes without an offset",
        )
    if received_to <= received_from:
        raise HTTPException(status_code=422, detail="received_to must be greater than received_from")

    items, total = list_instrument_result_sets(
        db,
        received_from=received_from,
        received_to=received_to,
        id_instrument=id_instrument,
        page=page,
        page_size=page_size,
    )
    return PaginatedInstrumentResultSetResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        identity_notice=IDENTITY_NOTICE,
    )


@router.get("/{id_result_set}", response_model=InstrumentResultSetDetail)
def get_instrument_result(id_result_set: int, db: Session = Depends(get_db)):
    """One unlinked XN-550 result set: items, deliveries, provenance, identity notice."""
    detail = get_instrument_result_set(db, id_result_set)
    if detail is None:
        raise HTTPException(status_code=404, detail="Instrument result set not found")
    return detail
