from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.core.database import get_db
from app.models import Patient, Visit, Order, TestRun, Result
from app.schemas.clinical import HistoryPatientResponse

router = APIRouter(prefix="/patients", tags=["patients"])

@router.get("/{nomor_rm}/history", response_model=HistoryPatientResponse)
def get_patient_history(nomor_rm: str, db: Session = Depends(get_db)):
    stmt = select(Patient).options(
        selectinload(Patient.visits)
        .selectinload(Visit.orders)
        .selectinload(Order.test_runs)
        .selectinload(TestRun.results),
        selectinload(Patient.visits)
        .selectinload(Visit.orders)
        .selectinload(Order.test_runs)
        .selectinload(TestRun.instrument)
    ).where(Patient.nomor_rm == nomor_rm)
    
    patient = db.scalar(stmt)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    return patient
