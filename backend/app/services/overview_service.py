"""M8.4 — instrument-scoped operational Order overview.

Row grain
    One row == one Order. An Order is included when the requested instrument has
    at least one TestRun for it (EXISTS semi-join, no row fan-out).

Effective run
    The run M7's detail view would select first for that order, restricted to
    the requested instrument:

        ORDER BY is_final DESC, run_sequence DESC, id_run DESC   -> first row

    run_sequence is trustworthy (NOT NULL, MAX+1 per order, UNIQUE per order),
    so waktu_run is never an ordering key here; id_run DESC is a defensive
    deterministic tie-breaker only.

Finality / delivery
    is_final           = effective_run.is_final
    delivery_status    = effective_run.delivery_status  IF the effective run is
                         final, else NULL
    delivered_at       = effective_run.delivered_at     IF the effective run is
                         final, else NULL
    A no-final-run order is a normal state, not an error.

Abnormal count
    COUNT(results for the effective run WHERE flag_abnormalitas IS NOT NULL).
    Never summed across reruns or the whole order. Parser semantics already
    normalize 'N' / '' / whitespace to NULL and never persist technical
    metadata as a Result.

Dates / timezone
    Filter on Order.waktu_order (server-controlled, NOT NULL, one per Order).
    Range is half-open: waktu_order >= date_from AND waktu_order < date_to.
    Timestamps are treated as server-local naive datetimes: the schema uses
    TIMESTAMP WITHOUT TIME ZONE and the deployment is single-site on-premise.
    No implicit "today".
"""
from datetime import datetime
from typing import List, Tuple

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.models import Order, Patient, Result, TestRun, Visit


def _exists_run_for_instrument(instrument_id: int):
    """EXISTS(a TestRun for this Order produced by the requested instrument)."""
    return (
        select(1)
        .where(
            TestRun.id_order == Order.id_order,
            TestRun.id_instrument == instrument_id,
        )
        .exists()
    )


def _effective_run_lateral(instrument_id: int):
    """LATERAL: the single effective run for the correlated Order, scoped to the
    requested instrument, using M7's finality-first ordering."""
    return (
        select(
            TestRun.id_run.label("id_run"),
            TestRun.run_sequence.label("run_sequence"),
            TestRun.waktu_run.label("waktu_run"),
            TestRun.is_final.label("is_final"),
            TestRun.delivery_status.label("delivery_status"),
            TestRun.delivered_at.label("delivered_at"),
        )
        .where(
            TestRun.id_order == Order.id_order,
            TestRun.id_instrument == instrument_id,
        )
        .order_by(
            TestRun.is_final.desc(),
            TestRun.run_sequence.desc(),
            TestRun.id_run.desc(),
        )
        .limit(1)
        .lateral("er")
    )


def get_instrument_order_overview(
    session: Session,
    *,
    instrument_id: int,
    date_from: datetime,
    date_to: datetime,
    page: int,
    page_size: int,
) -> Tuple[List[dict], int]:
    """Return (rows, total) for one page of the instrument's order worklist.

    ``total`` is the true number of qualifying Order rows and is never inflated
    by TestRun/Result joins.
    """
    date_filter = (
        Order.waktu_order >= date_from,
        Order.waktu_order < date_to,
    )

    total = session.scalar(
        select(func.count(Order.id_order)).where(
            _exists_run_for_instrument(instrument_id),
            *date_filter,
        )
    )

    er = _effective_run_lateral(instrument_id)
    abnormal = (
        select(func.count().label("abnormal_count"))
        .where(
            Result.id_run == er.c.id_run,
            Result.flag_abnormalitas.is_not(None),
        )
        .lateral("ab")
    )

    result_rows = session.execute(
        select(
            Order.id_order,
            Order.waktu_order,
            Order.status_order,
            Patient.nomor_rm,
            Patient.nama_lengkap,
            Visit.no_registrasi,
            Visit.id_visit,
            er.c.id_run.label("effective_run_id"),
            er.c.run_sequence.label("effective_run_sequence"),
            er.c.waktu_run.label("effective_run_waktu_run"),
            er.c.is_final.label("effective_is_final"),
            er.c.delivery_status.label("effective_delivery_status"),
            er.c.delivered_at.label("effective_delivered_at"),
            func.coalesce(abnormal.c.abnormal_count, 0).label("abnormal_count"),
        )
        .select_from(Order)
        .join(Visit, Visit.id_visit == Order.id_visit)
        .join(Patient, Patient.id_pasien == Visit.id_pasien)
        .outerjoin(er, true())
        .outerjoin(abnormal, true())
        .where(
            _exists_run_for_instrument(instrument_id),
            *date_filter,
        )
        .order_by(Order.waktu_order.desc(), Order.id_order.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()

    items: List[dict] = []
    for row in result_rows:
        is_final = bool(row.effective_is_final)
        items.append(
            {
                "id_order": row.id_order,
                "waktu_order": row.waktu_order,
                "status_order": row.status_order,
                "nomor_rm": row.nomor_rm,
                "nama_lengkap": row.nama_lengkap,
                "no_registrasi": row.no_registrasi,
                "id_visit": row.id_visit,
                "effective_run_id": row.effective_run_id,
                "effective_run_sequence": row.effective_run_sequence,
                "effective_run_waktu_run": row.effective_run_waktu_run,
                "is_final": is_final,
                "delivery_status": row.effective_delivery_status if is_final else None,
                "delivered_at": row.effective_delivered_at if is_final else None,
                "abnormal_count": row.abnormal_count,
            }
        )

    return items, total
