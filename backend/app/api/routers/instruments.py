from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.models.instrument import Instrument
from app.schemas.clinical import InstrumentStatusResponse

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

