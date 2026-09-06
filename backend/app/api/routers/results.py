from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from sqlalchemy import select, desc, func
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.models import Result, TestRun, Order, Visit, Patient, Instrument
from app.schemas.clinical import PaginatedResultResponse

router = APIRouter(prefix="/results", tags=["results"])

@router.get("", response_model=PaginatedResultResponse)
def get_results(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    nomor_rm: Optional[str] = Query(None, description="Filter by patient nomor_rm"),
    id_instrument: Optional[int] = Query(None, description="Filter by instrument ID"),
    id_order: Optional[int] = Query(None, description="Filter by order ID"),
    id_run: Optional[int] = Query(None, description="Filter by test run ID"),
    is_final: Optional[bool] = Query(None, description="Filter by test run final status"),
    delivery_status: Optional[str] = Query(None, description="Filter by delivery status"),
    start_date: Optional[datetime] = Query(None, description="Start date for waktu_hasil"),
    end_date: Optional[datetime] = Query(None, description="End date for waktu_hasil")
):
    # Base query for results with joined loads to avoid N+1
    stmt = select(Result).options(
        joinedload(Result.test_run).joinedload(TestRun.order).joinedload(Order.visit).joinedload(Visit.patient),
        joinedload(Result.test_run).joinedload(TestRun.instrument)
    )
    count_stmt = select(func.count(Result.id_hasil))

    # Determine if we need explicit joins for filtering
    needs_test_run_join = any(x is not None for x in [id_instrument, id_order, is_final, delivery_status, nomor_rm])
    needs_order_join = nomor_rm is not None
    needs_visit_join = nomor_rm is not None
    needs_patient_join = nomor_rm is not None

    if needs_test_run_join:
        stmt = stmt.join(Result.test_run)
        count_stmt = count_stmt.join(Result.test_run)
    if needs_order_join:
        stmt = stmt.join(TestRun.order)
        count_stmt = count_stmt.join(TestRun.order)
    if needs_visit_join:
        stmt = stmt.join(Order.visit)
        count_stmt = count_stmt.join(Order.visit)
    if needs_patient_join:
        stmt = stmt.join(Visit.patient)
        count_stmt = count_stmt.join(Visit.patient)

    # Apply filters
    if nomor_rm is not None:
        stmt = stmt.where(Patient.nomor_rm == nomor_rm)
        count_stmt = count_stmt.where(Patient.nomor_rm == nomor_rm)
    if id_instrument is not None:
        stmt = stmt.where(TestRun.id_instrument == id_instrument)
        count_stmt = count_stmt.where(TestRun.id_instrument == id_instrument)
    if id_order is not None:
        stmt = stmt.where(TestRun.id_order == id_order)
        count_stmt = count_stmt.where(TestRun.id_order == id_order)
    if id_run is not None:
        stmt = stmt.where(Result.id_run == id_run)
        count_stmt = count_stmt.where(Result.id_run == id_run)
    if is_final is not None:
        stmt = stmt.where(TestRun.is_final == is_final)
        count_stmt = count_stmt.where(TestRun.is_final == is_final)
    if delivery_status is not None:
        stmt = stmt.where(TestRun.delivery_status == delivery_status)
        count_stmt = count_stmt.where(TestRun.delivery_status == delivery_status)
    if start_date is not None:
        stmt = stmt.where(Result.waktu_hasil >= start_date)
        count_stmt = count_stmt.where(Result.waktu_hasil >= start_date)
    if end_date is not None:
        stmt = stmt.where(Result.waktu_hasil <= end_date)
        count_stmt = count_stmt.where(Result.waktu_hasil <= end_date)

    # Calculate total
    total = db.scalar(count_stmt)

    # Ordering and Pagination
    stmt = stmt.order_by(desc(Result.waktu_hasil))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    
    db_results = db.scalars(stmt).unique().all()
    
    # Construct response
    items = []
    for res in db_results:
        items.append({
            "id_hasil": res.id_hasil,
            "parameter_tes": res.parameter_tes,
            "nilai_hasil": res.nilai_hasil,
            "satuan": res.satuan,
            "flag_abnormalitas": res.flag_abnormalitas,
            "reference_range_snapshot": res.reference_range_snapshot,
            "waktu_hasil": res.waktu_hasil,
            "test_run": res.test_run,
            "instrument": res.test_run.instrument,
            "order": res.test_run.order,
            "visit": res.test_run.order.visit,
            "patient": res.test_run.order.visit.patient
        })

    return PaginatedResultResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total
    )
