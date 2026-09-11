"""M8.4 — instrument-scoped Order overview API tests (PostgreSQL only).

Row grain = one Order. Effective run = M7's finality-first selection
(is_final DESC, run_sequence DESC, id_run DESC) restricted to the requested
instrument. Delivery status / delivered_at / abnormal_count derive from the
effective run only.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.models import Instrument, Order, Patient, Result, TestRun, Visit
from app.models.base import Base

PG_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(PG_URL)
SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)

WIDE_FROM = "2026-01-01T00:00:00"
WIDE_TO = "2027-01-01T00:00:00"


# --- fixtures -------------------------------------------------------------

@pytest.fixture(scope="module")
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean(_schema):
    with SessionTest() as s:
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()
    yield


@pytest.fixture
def session():
    s = SessionTest()
    try:
        yield s
    finally:
        s.close()


class _StubAnalystUser:
    """M9.1a bypass — this module tests overview query logic, not
    authentication. See tests/api/test_auth_security.py for real auth
    coverage."""

    id_user = 0
    username = "test-analyst"
    role = "ANALYST"
    is_active = True


@pytest.fixture
def client(session):
    def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_current_user] = lambda: _StubAnalystUser()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


# --- builders -----------------------------------------------------------

def mk_instrument(session, nama="Mindray BC-5150"):
    inst = Instrument(nama_mesin=nama, protokol="HL7", tipe_koneksi="TCP/IP")
    session.add(inst)
    session.flush()
    return inst


def mk_patient(session, rm, nama="Patient"):
    p = Patient(nomor_rm=rm, nama_lengkap=nama)
    session.add(p)
    session.flush()
    return p


def mk_visit(session, patient, reg, waktu=datetime(2026, 6, 1, 8, 0)):
    v = Visit(id_pasien=patient.id_pasien, no_registrasi=reg, waktu_kunjungan=waktu)
    session.add(v)
    session.flush()
    return v


def mk_order(session, visit, waktu_order=datetime(2026, 6, 1, 9, 0), status="Diproses"):
    o = Order(id_visit=visit.id_visit, status_order=status, waktu_order=waktu_order)
    session.add(o)
    session.flush()
    return o


def mk_run(session, order, instrument, seq, *, is_final=False,
           delivery_status="pending", delivered_at=None, waktu_run=None):
    r = TestRun(
        id_order=order.id_order,
        id_instrument=instrument.id_instrument,
        run_sequence=seq,
        is_final=is_final,
        delivery_status=delivery_status,
        delivered_at=delivered_at,
        waktu_run=waktu_run,
    )
    session.add(r)
    session.flush()
    return r


def mk_result(session, run, param="WBC", flag=None, nilai="1.0"):
    res = Result(id_run=run.id_run, parameter_tes=param, nilai_hasil=nilai,
                 flag_abnormalitas=flag)
    session.add(res)
    session.flush()
    return res


def fetch(client, instrument_id, *, date_from=WIDE_FROM, date_to=WIDE_TO, **params):
    return client.get(
        f"/api/instruments/{instrument_id}/orders",
        params={"date_from": date_from, "date_to": date_to, **params},
    )


# =====================================================================
# P0
# =====================================================================

def test_p0_01_one_order_one_run(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1", "Alice"), "REG1")
    o = mk_order(session, v)
    run = mk_run(session, o, inst, 1)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    row = body["items"][0]
    assert row["id_order"] == o.id_order
    assert row["effective_run_id"] == run.id_run
    assert row["effective_run_sequence"] == 1
    assert row["is_final"] is False
    assert row["delivery_status"] is None
    assert row["abnormal_count"] == 0
    assert row["nomor_rm"] == "RM1"
    assert row["nama_lengkap"] == "Alice"
    assert row["no_registrasi"] == "REG1"
    assert row["id_visit"] == v.id_visit


def test_p0_02_one_order_three_runs_no_fan_out(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    mk_run(session, o, inst, 1)
    mk_run(session, o, inst, 2)
    r3 = mk_run(session, o, inst, 3)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["effective_run_id"] == r3.id_run
    assert body["items"][0]["effective_run_sequence"] == 3


def test_p0_03_final_run_not_highest_sequence_is_effective(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    final_run = mk_run(session, o, inst, 1, is_final=True, delivery_status="pending")
    mk_run(session, o, inst, 2)
    mk_run(session, o, inst, 3)
    session.commit()

    row = fetch(client, inst.id_instrument).json()["items"][0]
    assert row["effective_run_id"] == final_run.id_run
    assert row["effective_run_sequence"] == 1
    assert row["is_final"] is True


def test_p0_04_failed_history_final_success_delivery_from_final(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    mk_run(session, o, inst, 1, is_final=False, delivery_status="failed")
    delivered = datetime(2026, 6, 1, 12, 0)
    final_run = mk_run(session, o, inst, 2, is_final=True,
                       delivery_status="delivered", delivered_at=delivered)
    session.commit()

    row = fetch(client, inst.id_instrument).json()["items"][0]
    assert row["effective_run_id"] == final_run.id_run
    assert row["is_final"] is True
    assert row["delivery_status"] == "delivered"
    assert row["delivered_at"] == delivered.isoformat()


def test_p0_05_no_final_run(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    mk_run(session, o, inst, 1)
    mk_run(session, o, inst, 2)
    r3 = mk_run(session, o, inst, 3, delivery_status="pending")
    session.commit()

    row = fetch(client, inst.id_instrument).json()["items"][0]
    assert row["effective_run_id"] == r3.id_run
    assert row["effective_run_sequence"] == 3
    assert row["is_final"] is False
    assert row["delivery_status"] is None
    assert row["delivered_at"] is None


def test_p0_06_two_orders_one_visit_two_rows(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o1 = mk_order(session, v, waktu_order=datetime(2026, 6, 1, 9, 0))
    o2 = mk_order(session, v, waktu_order=datetime(2026, 6, 1, 10, 0))
    mk_run(session, o1, inst, 1)
    mk_run(session, o2, inst, 1)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 2
    assert {r["id_order"] for r in body["items"]} == {o1.id_order, o2.id_order}


def test_p0_07_abnormal_count_all_null_is_zero(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    run = mk_run(session, o, inst, 1)
    mk_result(session, run, "WBC", flag=None)
    mk_result(session, run, "RBC", flag=None)
    session.commit()

    assert fetch(client, inst.id_instrument).json()["items"][0]["abnormal_count"] == 0


def test_p0_08_abnormal_count_mixed_flags(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    run = mk_run(session, o, inst, 1)
    mk_result(session, run, "WBC", flag="H")
    mk_result(session, run, "RBC", flag=None)
    mk_result(session, run, "PLT", flag="L")
    mk_result(session, run, "HGB", flag=None)
    session.commit()

    assert fetch(client, inst.id_instrument).json()["items"][0]["abnormal_count"] == 2


def test_p0_09_abnormals_only_counted_for_effective_run(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    old_run = mk_run(session, o, inst, 1)
    mk_result(session, old_run, "WBC", flag="H")
    mk_result(session, old_run, "RBC", flag="L")
    mk_result(session, old_run, "PLT", flag="H")
    eff_run = mk_run(session, o, inst, 2)
    mk_result(session, eff_run, "WBC", flag="H")
    mk_result(session, eff_run, "RBC", flag=None)
    session.commit()

    row = fetch(client, inst.id_instrument).json()["items"][0]
    assert row["effective_run_id"] == eff_run.id_run
    assert row["abnormal_count"] == 1  # only the effective run, no double count


def test_p0_10_no_cross_instrument_leakage(client, session):
    inst_a = mk_instrument(session, "Mindray BC-5150")
    inst_b = mk_instrument(session, "Sysmex XN-550")
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    run_a = mk_run(session, o, inst_a, 1, is_final=False)
    run_b = mk_run(session, o, inst_b, 2, is_final=True, delivery_status="delivered",
                   delivered_at=datetime(2026, 6, 1, 12, 0))
    session.commit()

    row_a = fetch(client, inst_a.id_instrument).json()["items"][0]
    assert row_a["effective_run_id"] == run_a.id_run
    assert row_a["is_final"] is False
    assert row_a["delivery_status"] is None

    row_b = fetch(client, inst_b.id_instrument).json()["items"][0]
    assert row_b["effective_run_id"] == run_b.id_run
    assert row_b["is_final"] is True
    assert row_b["delivery_status"] == "delivered"


def test_p0_11_date_from_boundary_inclusive(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v, waktu_order=datetime(2026, 6, 10, 0, 0, 0))
    mk_run(session, o, inst, 1)
    session.commit()

    hit = fetch(client, inst.id_instrument,
                date_from="2026-06-10T00:00:00", date_to="2026-06-11T00:00:00").json()
    assert hit["total"] == 1

    miss = fetch(client, inst.id_instrument,
                 date_from="2026-06-10T00:00:01", date_to="2026-06-11T00:00:00").json()
    assert miss["total"] == 0


def test_p0_12_date_to_boundary_exclusive(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v, waktu_order=datetime(2026, 6, 10, 0, 0, 0))
    mk_run(session, o, inst, 1)
    session.commit()

    excluded = fetch(client, inst.id_instrument,
                     date_from="2026-06-09T00:00:00", date_to="2026-06-10T00:00:00").json()
    assert excluded["total"] == 0

    included = fetch(client, inst.id_instrument,
                     date_from="2026-06-09T00:00:00", date_to="2026-06-10T00:00:01").json()
    assert included["total"] == 1


def test_p0_13_identical_waktu_order_deterministic_id_desc(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    same = datetime(2026, 6, 1, 9, 0, 0)
    o1 = mk_order(session, v, waktu_order=same)
    o2 = mk_order(session, v, waktu_order=same)
    mk_run(session, o1, inst, 1)
    mk_run(session, o2, inst, 1)
    session.commit()

    ids = [r["id_order"] for r in fetch(client, inst.id_instrument).json()["items"]]
    assert ids == sorted([o1.id_order, o2.id_order], reverse=True)


def test_p0_14_multi_page_pagination_no_dupes_no_gaps(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    orders = []
    for i in range(5):
        o = mk_order(session, v, waktu_order=datetime(2026, 6, 1, 9 + i, 0))
        mk_run(session, o, inst, 1)
        orders.append(o.id_order)
    session.commit()

    seen = []
    for page in (1, 2, 3):
        body = fetch(client, inst.id_instrument, page=page, page_size=2).json()
        assert body["total"] == 5
        assert body["page"] == page
        assert body["page_size"] == 2
        seen.extend(r["id_order"] for r in body["items"])

    assert len(seen) == 5
    assert len(set(seen)) == 5
    assert set(seen) == set(orders)
    # newest-first, id_order desc within equal timestamps (here strictly newest first)
    assert seen == sorted(orders, reverse=True)


def test_p0_15_total_not_inflated_by_runs_or_results(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    for oi in range(2):
        o = mk_order(session, v, waktu_order=datetime(2026, 6, 1, 9 + oi, 0))
        for si in range(1, 4):
            run = mk_run(session, o, inst, si)
            mk_result(session, run, "WBC", flag="H")
            mk_result(session, run, "RBC", flag=None)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


# =====================================================================
# P1
# =====================================================================

def test_p1_16_two_visits_same_patient_two_rows(client, session):
    inst = mk_instrument(session)
    p = mk_patient(session, "RM1", "Alice")
    v1 = mk_visit(session, p, "REG1")
    v2 = mk_visit(session, p, "REG2")
    o1 = mk_order(session, v1, waktu_order=datetime(2026, 6, 1, 9, 0))
    o2 = mk_order(session, v2, waktu_order=datetime(2026, 6, 2, 9, 0))
    mk_run(session, o1, inst, 1)
    mk_run(session, o2, inst, 1)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 2
    assert {r["id_visit"] for r in body["items"]} == {v1.id_visit, v2.id_visit}
    assert all(r["nomor_rm"] == "RM1" for r in body["items"])


def test_p1_17_same_patient_multiple_orders_one_row_each(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    orders = []
    for i in range(3):
        o = mk_order(session, v, waktu_order=datetime(2026, 6, 1, 9 + i, 0))
        mk_run(session, o, inst, 1)
        mk_run(session, o, inst, 2)
        orders.append(o.id_order)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 3
    assert sorted(r["id_order"] for r in body["items"]) == sorted(orders)


def test_p1_18_same_name_different_mrn_distinct_rows(client, session):
    inst = mk_instrument(session)
    p1 = mk_patient(session, "RM-A", "John Doe")
    p2 = mk_patient(session, "RM-B", "John Doe")
    o1 = mk_order(session, mk_visit(session, p1, "REG1"), waktu_order=datetime(2026, 6, 1, 9, 0))
    o2 = mk_order(session, mk_visit(session, p2, "REG2"), waktu_order=datetime(2026, 6, 1, 10, 0))
    mk_run(session, o1, inst, 1)
    mk_run(session, o2, inst, 1)
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert body["total"] == 2
    assert {r["nomor_rm"] for r in body["items"]} == {"RM-A", "RM-B"}


def test_p1_19_valid_request_no_matching_orders(client, session):
    inst = mk_instrument(session)
    session.commit()

    resp = fetch(client, inst.id_instrument)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_p1_19b_order_exists_but_only_for_other_instrument(client, session):
    inst_a = mk_instrument(session, "A")
    inst_b = mk_instrument(session, "B")
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    mk_run(session, o, inst_b, 1)
    session.commit()

    body = fetch(client, inst_a.id_instrument).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_p1_20_unknown_instrument_404(client, session):
    session.commit()
    resp = fetch(client, 999999)
    assert resp.status_code == 404


def test_p1_21_effective_run_with_zero_results(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    o = mk_order(session, v)
    mk_run(session, o, inst, 1)
    session.commit()

    row = fetch(client, inst.id_instrument).json()["items"][0]
    assert row["abnormal_count"] == 0


def test_p1_22_repeated_identical_query_is_deterministic(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1"), "REG1")
    same = datetime(2026, 6, 1, 9, 0)
    for _ in range(4):
        o = mk_order(session, v, waktu_order=same)
        mk_run(session, o, inst, 1)
    session.commit()

    first = [r["id_order"] for r in fetch(client, inst.id_instrument).json()["items"]]
    for _ in range(3):
        again = [r["id_order"] for r in fetch(client, inst.id_instrument).json()["items"]]
        assert again == first


# =====================================================================
# P2
# =====================================================================

def test_p2_23_invalid_date_range_422(client, session):
    inst = mk_instrument(session)
    session.commit()

    assert fetch(client, inst.id_instrument,
                 date_from=WIDE_TO, date_to=WIDE_FROM).status_code == 422
    assert fetch(client, inst.id_instrument,
                 date_from=WIDE_FROM, date_to=WIDE_FROM).status_code == 422


def test_p2_24_page_size_over_100_is_422(client, session):
    inst = mk_instrument(session)
    session.commit()
    assert fetch(client, inst.id_instrument, page_size=101).status_code == 422
    assert fetch(client, inst.id_instrument, page_size=0).status_code == 422
    assert fetch(client, inst.id_instrument, page=0).status_code == 422


def test_p2_25_missing_date_params_422(client, session):
    inst = mk_instrument(session)
    session.commit()
    assert client.get(f"/api/instruments/{inst.id_instrument}/orders").status_code == 422
    assert client.get(
        f"/api/instruments/{inst.id_instrument}/orders",
        params={"date_from": WIDE_FROM},
    ).status_code == 422


def test_p2_26_response_field_types(client, session):
    inst = mk_instrument(session)
    v = mk_visit(session, mk_patient(session, "RM1", "Alice"), "REG1")
    o = mk_order(session, v)
    run = mk_run(session, o, inst, 1, is_final=True, delivery_status="delivered",
                 delivered_at=datetime(2026, 6, 1, 12, 0), waktu_run=datetime(2026, 6, 1, 9, 30))
    mk_result(session, run, "WBC", flag="H")
    session.commit()

    body = fetch(client, inst.id_instrument).json()
    assert isinstance(body["items"], list) and isinstance(body["total"], int)
    row = body["items"][0]
    assert isinstance(row["id_order"], int)
    assert isinstance(row["status_order"], str)
    assert isinstance(row["nomor_rm"], str)
    assert isinstance(row["id_visit"], int)
    assert isinstance(row["effective_run_id"], int)
    assert isinstance(row["effective_run_sequence"], int)
    assert isinstance(row["is_final"], bool)
    assert isinstance(row["delivery_status"], str)
    assert isinstance(row["abnormal_count"], int)
