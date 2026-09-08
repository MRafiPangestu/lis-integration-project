"""Instrument message ingestion (M8.2).

Three logical transaction stages on one Session:

* **T1** — insert the raw ``InstrumentMessage`` and commit it on its own, so the
  audit row survives any later failure.
* **T2** — parse, classify, and (only for ``PATIENT_RESULT``) build the
  ``Order -> Test Run -> Result`` hierarchy, then commit.
* **T3** — if T2 fails, roll it back, then update the already-committed raw row
  with the failure state and commit that.

Classification is a separate axis from ``parse_status`` and is instrument-agnostic
(see :mod:`app.integration.classification`). Only ``PATIENT_RESULT`` enters
clinical persistence; every other class is raw-persisted only.
"""
import logging
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integration.classification import Classification, MessageClass
from app.integration.mllp import extract_control_id
from app.integration.parsers import ParsedHL7
from app.integration.protocols import InstrumentTransport
from app.models import InstrumentMessage, Order, Patient, Result, TestRun, Visit

log = logging.getLogger(__name__)

ParserFn = Callable[[str], Optional[ParsedHL7]]
ClassifyFn = Callable[[Optional[ParsedHL7]], Classification]

RULE_PARSER_ERROR = "unparseable.parser_error"


def _exc_summary(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]


def _apply_classification(msg: InstrumentMessage, classification: Classification) -> None:
    msg.message_class = classification.message_class.value
    msg.classification_rule = classification.classification_rule


def _next_run_sequence(session: Session, id_order: int) -> int:
    """run_sequence = MAX(run_sequence) + 1 per order (unchanged formula)."""
    return session.scalar(
        select(func.coalesce(func.max(TestRun.run_sequence), 0) + 1).where(
            TestRun.id_order == id_order
        )
    )


def process_message(
    raw_frame: bytes,
    transport: InstrumentTransport,
    instrument_id: int,
    session: Session,
    *,
    parser: ParserFn,
    identity_prefix: str,
    classify_fn: ClassifyFn,
) -> None:
    raw_text = raw_frame.decode("utf-8", errors="replace")
    # Protocol-level control id, independent of the vendor parser: used for
    # failure ACKs even when the parser returns nothing or raises.
    raw_control_id = extract_control_id(raw_text)

    # --- T1 -------------------------------------------------------------
    msg = InstrumentMessage(
        id_instrument=instrument_id,
        raw_message=raw_text,
        parse_status="Pending",
    )
    session.add(msg)
    session.commit()
    message_id = msg.id_message

    classification: Optional[Classification] = None
    try:
        # --- T2 -------------------------------------------------------
        parsed = parser(raw_text)
        classification = classify_fn(parsed)
        _apply_classification(msg, classification)

        if classification.message_class == MessageClass.UNPARSEABLE:
            msg.parse_status = "Failed"
            msg.error_detail = "Validation failed: Could not extract MSH.10"
            session.commit()
            if raw_control_id is None:
                log.warning(
                    "instrument %s message %s: unparseable and no MSH-10 in raw "
                    "frame; sending AE with empty control id",
                    instrument_id, message_id,
                )
            transport.send_ack(raw_control_id or "", success=False, error="Unparseable message")
            return

        control_id = parsed.control_id

        if classification.message_class != MessageClass.PATIENT_RESULT:
            # NON_PATIENT / UNCLASSIFIED: raw persisted, no clinical rows.
            msg.parse_status = "Success"
            session.commit()
            transport.send_ack(control_id, success=True)
            return

        # --- PATIENT_RESULT: clinical persistence (behaviour unchanged) ---
        if not parsed.results:
            msg.parse_status = "Failed"
            msg.error_detail = "Validation failed: No clinical results found"
            session.commit()
            transport.send_ack(control_id, success=False, error="No clinical results found")
            return

        if not parsed.order.specimen_no or not parsed.order.waktu_run:
            msg.parse_status = "Failed"
            msg.error_detail = "Validation failed: Missing OBR.3 or OBR.7"
            session.commit()
            transport.send_ack(control_id, success=False, error="Missing OBR.3 or OBR.7")
            return

        no_registrasi = f"{identity_prefix}{parsed.order.specimen_no}"

        # Exact-retransmission idempotency (unchanged).
        existing_run = session.scalar(
            select(TestRun.id_run)
            .join(Order, TestRun.id_order == Order.id_order)
            .join(Visit, Order.id_visit == Visit.id_visit)
            .where(
                TestRun.id_instrument == instrument_id,
                Visit.no_registrasi == no_registrasi,
                TestRun.waktu_run == parsed.order.waktu_run,
            )
        )
        if existing_run:
            msg.parse_status = "Success"
            msg.error_detail = "Retransmission: Source measurement already exists"
            session.commit()
            transport.send_ack(control_id, success=True)
            return

        # Find or create Patient (identity resolution unchanged).
        nomor_rm = parsed.patient.nomor_rm
        is_synthetic = False
        if not nomor_rm:
            nomor_rm = no_registrasi
            is_synthetic = True

        patient = session.scalar(select(Patient).where(Patient.nomor_rm == nomor_rm))
        if not patient:
            patient = Patient(
                nomor_rm=nomor_rm,
                nama_lengkap=parsed.patient.nama_lengkap,
                jenis_kelamin=parsed.patient.jenis_kelamin,
            )
            session.add(patient)
            session.flush()

        visit = session.scalar(select(Visit).where(Visit.no_registrasi == no_registrasi))
        if not visit:
            visit = Visit(
                id_pasien=patient.id_pasien,
                no_registrasi=no_registrasi,
                waktu_kunjungan=parsed.order.waktu_run,
            )
            session.add(visit)
            session.flush()

        order = session.scalar(select(Order).where(Order.id_visit == visit.id_visit))
        if not order:
            order = Order(id_visit=visit.id_visit, status_order="Diproses")
            session.add(order)
            session.flush()

        run_sequence = _next_run_sequence(session, order.id_order)

        test_run = TestRun(
            id_order=order.id_order,
            id_instrument=instrument_id,
            id_message=message_id,
            run_sequence=run_sequence,
            waktu_run=parsed.order.waktu_run,
            is_final=False,
            delivery_status="pending",
        )
        session.add(test_run)
        session.flush()

        for r in parsed.results:
            session.add(Result(
                id_run=test_run.id_run,
                parameter_tes=r.parameter_tes,
                nilai_hasil=r.nilai_hasil,
                satuan=r.satuan,
                flag_abnormalitas=r.flag_abnormalitas,
                reference_range_snapshot=r.reference_range_snapshot,
            ))

        msg.parse_status = "Success"
        if is_synthetic:
            msg.error_detail = "SIMRS_IDENTITY_NOT_RESOLVED"

        session.commit()
        transport.send_ack(control_id, success=True)

    except Exception as exc:
        # --- T3 -----------------------------------------------------------
        # T2 is rolled back; the T1 raw row survives. Record the failure on it
        # without hiding the original exception.
        session.rollback()
        kind = "run_sequence uniqueness conflict" if (
            isinstance(exc, IntegrityError)
            and "run_sequence" in str(getattr(exc, "orig", exc))
        ) else ("integrity error" if isinstance(exc, IntegrityError) else "unexpected error")
        log.exception(
            "instrument %s message %s: %s during ingestion; raw message retained",
            instrument_id, message_id, kind,
        )
        try:
            if classification is not None:
                _apply_classification(msg, classification)
            else:
                # parser raised before classification ran
                _apply_classification(
                    msg, Classification(MessageClass.UNPARSEABLE, RULE_PARSER_ERROR)
                )
            msg.parse_status = "Failed"
            msg.error_detail = _exc_summary(exc)
            session.commit()
        except Exception:
            session.rollback()
            log.exception(
                "instrument %s message %s: could not record ingestion failure state",
                instrument_id, message_id,
            )

        transport.send_ack(raw_control_id or "", success=False, error="Ingestion error")
