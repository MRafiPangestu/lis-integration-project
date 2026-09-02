from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models import Patient, Visit, Order, TestRun, Result, InstrumentMessage
from app.integration.parsers.hl7 import parse_hl7_bc5150
from app.integration.protocols import InstrumentTransport
import traceback

def process_message(raw_frame: bytes, transport: InstrumentTransport, instrument_id: int, session: Session):
    raw_text = raw_frame.decode('utf-8', errors='replace')
    
    # Step 1: Save raw message
    msg = InstrumentMessage(
        id_instrument=instrument_id,
        raw_message=raw_text,
        parse_status='Pending'
    )
    session.add(msg)
    session.flush() # get id_message
    
    try:
        # Step 2: Parse HL7
        parsed = parse_hl7_bc5150(raw_text)
        
        if not parsed:
            msg.parse_status = 'Failed'
            msg.error_detail = 'Validation failed: Could not extract MSH.10'
            session.commit()
            return
            
        control_id = parsed.control_id
        
        if not parsed.results:
            msg.parse_status = 'Failed'
            msg.error_detail = 'Validation failed: No clinical results found'
            session.commit()
            transport.send_ack(control_id, success=False, error="No clinical results found")
            return
            
        if not parsed.order.specimen_no or not parsed.order.waktu_run:
            msg.parse_status = 'Failed'
            msg.error_detail = 'Validation failed: Missing OBR.3 or OBR.7'
            session.commit()
            transport.send_ack(control_id, success=False, error="Missing OBR.3 or OBR.7")
            return
            
        no_registrasi = f"BC5150-{parsed.order.specimen_no}"
        
        # Check idempotency: does this source measurement exist?
        existing_run = session.scalar(
            select(TestRun.id_run)
            .join(Order, TestRun.id_order == Order.id_order)
            .join(Visit, Order.id_visit == Visit.id_visit)
            .where(
                TestRun.id_instrument == instrument_id,
                Visit.no_registrasi == no_registrasi,
                TestRun.waktu_run == parsed.order.waktu_run
            )
        )
        
        if existing_run:
            msg.parse_status = 'Success'
            msg.error_detail = 'Retransmission: Source measurement already exists'
            session.commit()
            transport.send_ack(control_id, success=True)
            return

        # Find or create Patient
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
                jenis_kelamin=parsed.patient.jenis_kelamin
            )
            session.add(patient)
            session.flush()
            
        # Find or create Visit
        visit = session.scalar(select(Visit).where(Visit.no_registrasi == no_registrasi))
        if not visit:
            visit = Visit(
                id_pasien=patient.id_pasien,
                no_registrasi=no_registrasi,
                waktu_kunjungan=parsed.order.waktu_run
            )
            session.add(visit)
            session.flush()
            
        # Find or create Order
        order = session.scalar(select(Order).where(Order.id_visit == visit.id_visit))
        if not order:
            order = Order(
                id_visit=visit.id_visit,
                status_order='Diproses'
            )
            session.add(order)
            session.flush()
            
        # Calculate run sequence safely
        stmt = select(func.coalesce(func.max(TestRun.run_sequence), 0) + 1).where(
            TestRun.id_order == order.id_order
        )
        run_sequence = session.scalar(stmt)
        
        # Create TestRun
        test_run = TestRun(
            id_order=order.id_order,
            id_instrument=instrument_id,
            id_message=msg.id_message,
            run_sequence=run_sequence,
            waktu_run=parsed.order.waktu_run,
            is_final=False,
            delivery_status='pending'
        )
        session.add(test_run)
        session.flush()
        
        # Insert Results
        for r in parsed.results:
            result_row = Result(
                id_run=test_run.id_run,
                parameter_tes=r.parameter_tes,
                nilai_hasil=r.nilai_hasil,
                satuan=r.satuan,
                flag_abnormalitas=r.flag_abnormalitas,
                reference_range_snapshot=r.reference_range_snapshot
            )
            session.add(result_row)
            
        msg.parse_status = 'Success'
        if is_synthetic:
            msg.error_detail = 'SIMRS_IDENTITY_NOT_RESOLVED'
            
        session.commit()
        transport.send_ack(control_id, success=True)
        
    except Exception as e:
        session.rollback()
        # Attempt to save failure status
        try:
            msg = session.scalar(select(InstrumentMessage).where(InstrumentMessage.id_message == msg.id_message))
            if msg:
                msg.parse_status = 'Failed'
                msg.error_detail = f"Exception: {str(e)[:500]}"
                session.commit()
        except:
            session.rollback()
            
        # Try to send ACK AE if we have the parsed control_id
        try:
            control_id = parsed.control_id
            transport.send_ack(control_id, success=False, error=str(e))
        except:
            pass
