import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
        session.add_all([run1, run2])
        session.commit()
        
        # Keep IDs to use in tests
        global TEST_ORDER_ID, TEST_RUN1_ID, TEST_RUN2_ID
        TEST_ORDER_ID = order.id_order
        TEST_RUN1_ID = run1.id_run
        TEST_RUN2_ID = run2.id_run
        
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

