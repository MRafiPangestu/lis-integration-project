from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.models.instrument import Instrument
from app.schemas.clinical import InstrumentStatusResponse
from app.schemas.overview import PaginatedOrderOverviewResponse
from app.services.overview_service import get_instrument_order_overview

router = APIRouter(prefix="/instruments", tags=["instruments"])

@router.get("/status", response_model=List[InstrumentStatusResponse])
def get_instruments_status(db: Session = Depends(get_db)):
    stmt = select(Instrument).order_by(Instrument.id_instrument)
    instruments = db.scalars(stmt).all()
    
    results = []
    for inst in instruments:
        valid_statuses = {"CONNECTED", "RECONNECTING", "DISCONNECTED"}
        
        if inst.connection_status is None:
            norm_status = "UNKNOWN"
        elif inst.connection_status in valid_statuses:
            norm_status = inst.connection_status
        else:
            norm_status = "UNKNOWN"
            
        results.append({
            "id_instrument": inst.id_instrument,
            "nama_mesin": inst.nama_mesin,
            "protokol": inst.protokol,
            "tipe_koneksi": inst.tipe_koneksi,
            "connection_status": norm_status,
            "last_status_at": inst.last_status_at
        })
        
    return results

@router.get(
    "/{instrument_id}/orders",
    response_model=PaginatedOrderOverviewResponse,
)
def get_instrument_order_overview_endpoint(
    instrument_id: int,
    date_from: datetime = Query(
        ...,
        description=(
            "Inclusive lower bound for Order.waktu_order. Server-local naive "
            "datetime (schema is TIMESTAMP WITHOUT TIME ZONE); do not send an offset."
        ),
    ),
    date_to: datetime = Query(
        ...,
        description="Exclusive upper bound for Order.waktu_order (server-local naive datetime).",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Instrument-scoped operational Order worklist (M8.4).

    One row per Order for which the given instrument has produced at least one
    TestRun, within the half-open range ``[date_from, date_to)``. Read-only;
    derivation lives in ``overview_service``.
    """
    if date_to <= date_from:
        raise HTTPException(status_code=422, detail="date_to must be greater than date_from")

    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    items, total = get_instrument_order_overview(
        db,
        instrument_id=instrument_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return PaginatedOrderOverviewResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )
