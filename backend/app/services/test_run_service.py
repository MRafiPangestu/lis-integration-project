from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models import TestRun, Order

class TestRunService:
    @staticmethod
    def get_runs_by_order(session: Session, order_id: int) -> list[TestRun]:
        order = session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        stmt = select(TestRun).where(TestRun.id_order == order_id).order_by(TestRun.run_sequence.asc())
        return list(session.scalars(stmt).all())

    @staticmethod
    def finalize_run(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if test_run.is_final:
            return test_run
            
        # Application-level check (for cleaner errors)
        existing_final = session.scalar(
            select(TestRun).where(
                TestRun.id_order == test_run.id_order, 
                TestRun.is_final == True
            )
        )
        if existing_final:
            raise HTTPException(
                status_code=409, 
                detail=f"Order already has a final TestRun (id_run: {existing_final.id_run}). Please unfinalize it explicitly first."
            )
            
        try:
            test_run.is_final = True
            session.commit()
            session.refresh(test_run)
            return test_run
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Database constraint violation: Another run is already final for this order."
            )

    @staticmethod
    def unfinalize_run(session: Session, run_id: int) -> TestRun:
        test_run = session.get(TestRun, run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="TestRun not found")
            
        if not test_run.is_final:
            return test_run
            
        test_run.is_final = False
        session.commit()
        session.refresh(test_run)
        return test_run

