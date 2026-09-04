import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime

from app.main import app
from app.core.database import get_db
from app.models.base import Base
from app.models import Patient, Visit, Order, Instrument, TestRun, Result

# Use a test database
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def setup_database():
    # Clean recreate all tables based on ORM models
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Insert required base data for testing
    with TestingSessionLocal() as session:
        # Instrument
        inst = Instrument(nama_mesin="Mindray BC-5150", tipe_koneksi="TCP", protokol="HL7")
        session.add(inst)
        
        # Patient -> Visit -> Order
        pat = Patient(nomor_rm="RM-TEST-001", nama_lengkap="Test Patient")
        session.add(pat)
        session.flush()
        
        vis = Visit(id_pasien=pat.id_pasien, no_registrasi="REG-001", waktu_kunjungan="2023-01-01 10:00:00")
        session.add(vis)
        session.flush()
        
        order = Order(id_visit=vis.id_visit, status_order="Diproses")
        session.add(order)
        session.flush()
        
        # Create multiple test runs for the same order
        run1 = TestRun(id_order=order.id_order, id_instrument=inst.id_instrument, run_sequence=1, is_final=False)
        run2 = TestRun(id_order=order.id_order, id_instrument=inst.id_instrument, run_sequence=2, is_final=False)
        # Create a separate order and run for delivery testing isolation
        order2 = Order(id_visit=vis.id_visit, status_order="Diproses")
        session.add(order2)
        session.flush()
        run3 = TestRun(id_order=order2.id_order, id_instrument=inst.id_instrument, run_sequence=1, is_final=False, delivery_status="pending")
        session.add_all([run1, run2, run3])
        session.commit()
        
        # Add some results for immutability testing
        res = Result(id_run=run3.id_run, parameter_tes="WBC", nilai_hasil="5.0", satuan="10^9/L")
        session.add(res)
        session.commit()
        
        # Keep IDs to use in tests
        global TEST_ORDER_ID, TEST_RUN1_ID, TEST_RUN2_ID, TEST_RUN3_ID, TEST_RESULT_ID
        TEST_ORDER_ID = order.id_order
        TEST_RUN1_ID = run1.id_run
        TEST_RUN2_ID = run2.id_run
        TEST_RUN3_ID = run3.id_run
        TEST_RESULT_ID = res.id_hasil
        
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def db_session(setup_database):
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

# --- M4.1 Tests ---

def test_get_test_runs(client):
    response = client.get(f"/api/orders/{TEST_ORDER_ID}/test-runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id_run"] == TEST_RUN1_ID
    assert data[1]["id_run"] == TEST_RUN2_ID
    assert data[0]["is_final"] is False
    assert data[1]["is_final"] is False

def test_finalize_test_run(client):
    response = client.post(f"/api/test-runs/{TEST_RUN1_ID}/finalize")
    assert response.status_code == 200
    data = response.json()
    assert data["is_final"] is True

def test_finalize_idempotent(client):
    # Already finalized by previous test
    response = client.post(f"/api/test-runs/{TEST_RUN1_ID}/finalize")
    assert response.status_code == 200
    assert response.json()["is_final"] is True

def test_finalize_second_run_conflict(client):
    # Attempting to finalize run2 when run1 is already final should return 409
    response = client.post(f"/api/test-runs/{TEST_RUN2_ID}/finalize")
    assert response.status_code == 409
    assert "already has a final TestRun" in response.json()["detail"]

def test_unfinalize_test_run(client):
    response = client.post(f"/api/test-runs/{TEST_RUN1_ID}/unfinalize")
    assert response.status_code == 200
    assert response.json()["is_final"] is False

def test_unfinalize_idempotent(client):
    # Already unfinalized
    response = client.post(f"/api/test-runs/{TEST_RUN1_ID}/unfinalize")
    assert response.status_code == 200
    assert response.json()["is_final"] is False

def test_unfinalize_then_finalize_second_run(client):
    # Now that run1 is unfinalized, run2 can be finalized
    response = client.post(f"/api/test-runs/{TEST_RUN2_ID}/finalize")
    assert response.status_code == 200
    assert response.json()["is_final"] is True
    
    # And now run1 should get 409
    response = client.post(f"/api/test-runs/{TEST_RUN1_ID}/finalize")
    assert response.status_code == 409

def test_db_unique_constraint_fallback(db_session, client):
    from sqlalchemy.exc import IntegrityError
    
    run1 = db_session.get(TestRun, TEST_RUN1_ID)
    run2 = db_session.get(TestRun, TEST_RUN2_ID)
    
    # Ensure clean state
    run1.is_final = False
    run2.is_final = False
    db_session.commit()
    
    # We forcefully set run1 to final via DB (simulating race)
    run1.is_final = True
    db_session.commit()
    
    # Now run2 is also forced to True directly in DB layer to provoke IntegrityError
    run2.is_final = True
    try:
        db_session.commit()
        assert False, "Should have raised IntegrityError"
    except IntegrityError:
        db_session.rollback()
        
    # Reset state
    run1.is_final = False
    run2.is_final = False
    db_session.commit()

# --- M4.2 Tests ---

def test_delivery_non_final_rejected(client, db_session):
    # run3 is currently not final
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/start")
    assert response.status_code == 409
    assert "Only final TestRuns can be delivered" in response.json()["detail"]

def test_delivery_invalid_transitions_from_pending(client, db_session):
    # First finalize run3
    client.post(f"/api/test-runs/{TEST_RUN3_ID}/finalize")
    
    # pending -> delivered rejected
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/success")
    assert response.status_code == 409
    
    # pending -> failed rejected
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/fail")
    assert response.status_code == 409

def test_delivery_pending_to_sending(client, db_session):
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/start")
    assert response.status_code == 200
    assert response.json()["delivery_status"] == "sending"

def test_delivery_sending_duplicate_rejected(client, db_session):
    # Already sending
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/start")
    assert response.status_code == 409
    assert "Delivery is already in progress" in response.json()["detail"]

def test_delivery_unfinalize_blocked_when_sending(client):
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/unfinalize")
    assert response.status_code == 409
    assert "Cannot unfinalize" in response.json()["detail"]
    assert "sending" in response.json()["detail"]

def test_delivery_sending_to_failed(client):
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/fail")
    assert response.status_code == 200
    assert response.json()["delivery_status"] == "failed"

def test_delivery_unfinalize_allowed_when_failed(client):
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/unfinalize")
    assert response.status_code == 200
    # Must remain failed but unfinalized
    assert response.json()["is_final"] is False
    assert response.json()["delivery_status"] == "failed"

def test_delivery_failed_to_sending_retry(client):
    # Must finalize again before starting delivery
    client.post(f"/api/test-runs/{TEST_RUN3_ID}/finalize")
    
    # Retry delivery (failed -> sending)
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/start")
    assert response.status_code == 200
    assert response.json()["delivery_status"] == "sending"

def test_delivery_sending_to_delivered(client, db_session):
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/success")
    assert response.status_code == 200
    data = response.json()
    assert data["delivery_status"] == "delivered"
    assert data["delivered_at"] is not None

def test_delivery_delivered_terminal_transitions_rejected(client):
    # delivered -> sending rejected
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/start")
    assert response.status_code == 409
    assert "has already been delivered" in response.json()["detail"]
    
    # delivered -> failed rejected
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/delivery/fail")
    assert response.status_code == 409

def test_delivery_unfinalize_blocked_when_delivered(client):
    response = client.post(f"/api/test-runs/{TEST_RUN3_ID}/unfinalize")
    assert response.status_code == 409
    assert "Cannot unfinalize" in response.json()["detail"]
    assert "delivered" in response.json()["detail"]

def test_delivery_immutability(db_session):
    # Verify the clinical data was not touched
    result = db_session.get(Result, TEST_RESULT_ID)
    assert result.nilai_hasil == "5.0"
    assert result.satuan == "10^9/L"
