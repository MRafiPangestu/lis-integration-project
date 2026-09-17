"""XN-550 unlinked instrument results API (G2) — contract Appendix B.

PostgreSQL-only, against ``lis_marina_permata_test``. Uses the real login flow
(no ``get_current_user`` override) so JWT protection and roles are exercised
end to end. Data is created through the real G2 T2 stage from the committed,
redacted fixture and synthetic variants.
"""
from __future__ import annotations

import ast
import datetime
import json
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.core.security import hash_password
from app.integration.astm.assembler import CompleteMessage
from app.integration.parsers.xn550_astm import PARSER_KEY, PARSER_VERSION, classify_xn550, parse_xn550_astm
from app.integration.raw_capture import SessionContext, SqlRawCaptureStore
from app.integration.xn550_ingestion import Xn550ClassificationStage
from app.main import app
from app.models import (
    AuditEvent,
    Instrument,
    InstrumentResultSet,
    Order,
    Patient,
    Result,
    TestRun as ClinicalRun,  # aliased so pytest does not try to collect it
    User,
    Visit,
)
from app.models.base import Base

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
assert engine.url.database == "lis_marina_permata_test"

BACKEND = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = BACKEND / "tests" / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
T0 = datetime.datetime(2026, 9, 18, 9, 0, 0)
RANGE = {"received_from": "2026-09-18T09:00:00", "received_to": "2026-09-18T10:00:00"}
ANALYST_PASSWORD = "AnalystPass123"
ADMIN_PASSWORD = "AdminPass1234"

SUMMARY_KEYS = {
    "id_result_set", "id_instrument", "instrument_name", "received_at", "analysis_at", "sample_label",
    "association_status", "duplicate_status", "possible_duplicate_of", "item_count",
    "non_n_flag_item_count", "image_reference_count", "delivery_count",
}
DETAIL_KEYS = SUMMARY_KEYS | {"identity_notice", "items", "deliveries", "provenance"}
ITEM_KEYS = {"r_sequence", "test_code", "item_kind", "value", "units", "reference_range", "abnormal_flag", "result_status"}
DELIVERY_KEYS = {"id_message", "received_at", "id_session", "session_opened_at", "read_count"}
PROVENANCE_KEYS = {"id_message", "parser_key", "parser_version", "raw_sha256_prefix", "raw_length", "ack_policy"}
IDENTITY_NOTICE = "XN550_NO_VERIFIED_SPECIMEN_OR_PATIENT_IDENTIFIER"


def _variant(raw: bytes, *, stamp: str | None = None, label: str | None = None, shift_folder: bool = False) -> bytes:
    records = raw.decode("ascii").split("\r")
    if stamp:
        records = [record.replace("20260915023225", stamp) for record in records]
    if label:
        order = records[3].split("|")
        components = order[3].split("^")
        components[2] = label
        order[3] = "^".join(components)
        records[3] = "|".join(order)
    if shift_folder:
        index = next(i for i, record in enumerate(records) if "PNG&R&" in record)
        folder = records[index].split("PNG&R&", 1)[1][:8]
        records[index] = records[index].replace(f"PNG&R&{folder}", f"PNG&R&{int(folder) + 1:08d}", 1)
    return "\r".join(records).encode("ascii")


@pytest.fixture(scope="module")
def data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        session.add_all([
            User(username="xn-analyst", nama_lengkap="XN Analyst", password_hash=hash_password(ANALYST_PASSWORD),
                 role="ANALYST", is_active=True),
            User(username="xn-admin", nama_lengkap="XN Admin", password_hash=hash_password(ADMIN_PASSWORD),
                 role="ADMIN", is_active=True),
        ])
        xn = Instrument(nama_mesin="Sysmex XN-550")
        bc = Instrument(nama_mesin="Mindray BC-5150", protokol="HL7", tipe_koneksi="TCP")
        session.add_all([xn, bc])
        session.commit()
        xn_id, bc_id = xn.id_instrument, bc.id_instrument

    store = SqlRawCaptureStore(TestingSessionLocal)
    stage = Xn550ClassificationStage(
        session_factory=TestingSessionLocal, parser=parse_xn550_astm, policy=classify_xn550,
        parser_key=PARSER_KEY, parser_version=PARSER_VERSION, ingestion_stage="observations",
    )
    raw = FIXTURE.read_bytes()

    def deliver(payload: bytes, minutes: float, port: int) -> int:
        at = T0 + datetime.timedelta(minutes=minutes)
        id_session = store.open_session(SessionContext(xn_id, "listener", "127.0.0.1", 5001, "127.0.0.1", port,
                                                       "ack_per_read_on_receive", at))
        id_message = store.persist_event(
            xn_id, id_session, 1, CompleteMessage(payload, 0, len(payload), at, at, 2, None)
        )
        assert stage.process(id_message) == "XN550_ENVELOPE_CONFORMANT"
        return id_message

    ids = {
        "a": deliver(raw, 1, 49701),
        "a_again": deliver(raw, 2, 49702),
        "b_shifted": deliver(_variant(raw, shift_folder=True), 3, 49703),
        "c_other": deliver(_variant(raw, stamp="20260915041500", label="SYNTH-0003"), 4, 49704),
        "outside": deliver(_variant(raw, stamp="20260914101500", label="SYNTH-0009"), -2 * 24 * 60, 49705),
    }
    with TestingSessionLocal() as session:
        by_message = {s.id_message: s.id_result_set for s in session.scalars(select(InstrumentResultSet))}
    yield {"xn": xn_id, "bc": bc_id, "messages": ids, "sets": {k: by_message.get(v) for k, v in ids.items()}}
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(data):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]


def _token(client, username: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def analyst(client) -> dict:
    return _token(client, "xn-analyst", ANALYST_PASSWORD)


# --------------------------------------------------------------------------- #
# Authentication and roles (B.1)
# --------------------------------------------------------------------------- #


def test_anonymous_requests_are_rejected(client, data):
    assert client.get("/api/instrument-results", params=RANGE).status_code == 401
    assert client.get(f"/api/instrument-results/{data['sets']['a']}").status_code == 401
    assert client.get("/api/instrument-results", params=RANGE, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_every_authenticated_role_can_read(client, data):
    for username, password in (("xn-analyst", ANALYST_PASSWORD), ("xn-admin", ADMIN_PASSWORD)):
        headers = _token(client, username, password)
        assert client.get("/api/instrument-results", params=RANGE, headers=headers).status_code == 200
        assert client.get(f"/api/instrument-results/{data['sets']['a']}", headers=headers).status_code == 200


def test_only_get_routes_exist_for_instrument_results(client, analyst, data):
    routes = [route for route in app.routes if getattr(route, "path", "").startswith("/api/instrument-results")]
    assert {route.path for route in routes} == {"/api/instrument-results", "/api/instrument-results/{id_result_set}"}
    assert all(set(route.methods) == {"GET"} for route in routes)
    assert client.post("/api/instrument-results", json={}, headers=analyst).status_code == 405
    assert client.delete(f"/api/instrument-results/{data['sets']['a']}", headers=analyst).status_code == 405


# --------------------------------------------------------------------------- #
# List parameters (B.2)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("params", [{}, {"received_from": RANGE["received_from"]}, {"received_to": RANGE["received_to"]}])
def test_both_bounds_are_required(client, analyst, params):
    assert client.get("/api/instrument-results", params=params, headers=analyst).status_code == 422


@pytest.mark.parametrize(
    "bounds",
    [
        {"received_from": "2026-09-18T10:00:00", "received_to": "2026-09-18T10:00:00"},
        {"received_from": "2026-09-18T11:00:00", "received_to": "2026-09-18T10:00:00"},
        {"received_from": "2026-09-18T09:00:00+07:00", "received_to": "2026-09-18T10:00:00+07:00"},
        {"received_from": "2026-09-18T09:00:00Z", "received_to": "2026-09-18T10:00:00"},
    ],
)
def test_invalid_or_offset_bounds_are_rejected(client, analyst, bounds):
    assert client.get("/api/instrument-results", params=bounds, headers=analyst).status_code == 422


@pytest.mark.parametrize("extra", [{"page": 0}, {"page_size": 0}, {"page_size": 101}])
def test_pagination_limits(client, analyst, extra):
    assert client.get("/api/instrument-results", params={**RANGE, **extra}, headers=analyst).status_code == 422


def test_list_is_newest_first_with_offset_pagination_and_total(client, analyst, data):
    sets = data["sets"]
    pages = []
    for page in (1, 2, 3):
        response = client.get("/api/instrument-results", params={**RANGE, "page": page, "page_size": 2}, headers=analyst)
        assert response.status_code == 200
        body = response.json()
        assert (body["page"], body["page_size"], body["total"]) == (page, 2, 3)
        pages.append([item["id_result_set"] for item in body["items"]])
    assert pages == [[sets["c_other"], sets["b_shifted"]], [sets["a"]], []]
    default = client.get("/api/instrument-results", params=RANGE, headers=analyst).json()
    assert default["page_size"] == 50 and default["total"] == 3


def test_instrument_filter_and_unknown_instrument(client, analyst, data):
    def total(**params):
        response = client.get("/api/instrument-results", params={**RANGE, **params}, headers=analyst)
        assert response.status_code == 200
        return response.json()["total"]

    assert total(id_instrument=data["xn"]) == 3
    assert total(id_instrument=data["bc"]) == 0
    assert total(id_instrument=999999) == 0


def test_search_and_sort_parameters_have_no_effect(client, analyst):
    baseline = client.get("/api/instrument-results", params=RANGE, headers=analyst).json()
    for extra in (
        {"sample_label": "SYNTH-0003"}, {"sample_no": "XXXXXX"}, {"nomor_rm": "RM-1"}, {"no_registrasi": "R-1"},
        {"name": "SYNTH"}, {"patient": "SYNTH"}, {"q": "SYNTH-0003"}, {"search": "XXXXXX"},
        {"sort": "sample_label"}, {"order_by": "analysis_at"},
    ):
        assert client.get("/api/instrument-results", params={**RANGE, **extra}, headers=analyst).json() == baseline


# --------------------------------------------------------------------------- #
# Response surface (B.2, B.3, B.4)
# --------------------------------------------------------------------------- #


def test_list_response_field_allowlist_and_duplicate_fields(client, analyst, data):
    body = client.get("/api/instrument-results", params=RANGE, headers=analyst).json()
    assert set(body) == {"items", "page", "page_size", "total", "identity_notice"}
    assert body["identity_notice"] == IDENTITY_NOTICE
    by_id = {item["id_result_set"]: item for item in body["items"]}
    for item in body["items"]:
        assert set(item) == SUMMARY_KEYS
        assert item["association_status"] == "UNRESOLVED"
        assert item["instrument_name"] == "Sysmex XN-550"
    a, b, c = (by_id[data["sets"][key]] for key in ("a", "b_shifted", "c_other"))
    assert (a["duplicate_status"], a["possible_duplicate_of"], a["delivery_count"]) == ("NONE", None, 2)
    assert (b["duplicate_status"], b["possible_duplicate_of"], b["delivery_count"]) == ("POSSIBLE_DUPLICATE", data["sets"]["a"], 1)
    assert (c["duplicate_status"], c["sample_label"]) == ("NONE", "SYNTH-0003")
    assert (a["item_count"], a["non_n_flag_item_count"], a["image_reference_count"]) == (42, 6, 4)
    assert a["analysis_at"] == "2026-09-15T02:32:25" and a["received_at"] == "2026-09-18T09:01:00"


def test_detail_response_field_allowlist_and_content(client, analyst, data):
    response = client.get(f"/api/instrument-results/{data['sets']['a']}", headers=analyst)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert body["identity_notice"] == IDENTITY_NOTICE and body["association_status"] == "UNRESOLVED"
    assert [item["r_sequence"] for item in body["items"]] == list(range(1, 43))
    for item in body["items"]:
        assert set(item) == ITEM_KEYS
        assert item["reference_range"] is None
        if item["item_kind"] == "IMAGE_REFERENCE":
            assert item["value"] is None and item["units"] is None
    wbc = next(item for item in body["items"] if item["test_code"] == "WBC")
    assert (wbc["value"], wbc["units"], wbc["abnormal_flag"], wbc["result_status"]) == ("11.30", "10*3/uL", "N", "F")
    assert [delivery["id_message"] for delivery in body["deliveries"]] == [data["messages"]["a"], data["messages"]["a_again"]]
    for delivery in body["deliveries"]:
        assert set(delivery) == DELIVERY_KEYS and delivery["read_count"] == 2
    provenance = body["provenance"]
    assert set(provenance) == PROVENANCE_KEYS
    assert provenance["id_message"] == data["messages"]["a"]
    assert (provenance["parser_key"], provenance["parser_version"]) == (PARSER_KEY, PARSER_VERSION)
    assert len(provenance["raw_sha256_prefix"]) == 12 and provenance["raw_length"] == len(FIXTURE.read_bytes())
    assert provenance["ack_policy"] == "ack_per_read_on_receive"


def test_unknown_result_set_is_404(client, analyst):
    response = client.get("/api/instrument-results/987654", headers=analyst)
    assert response.status_code == 404
    assert response.json() == {"detail": "Instrument result set not found"}


def test_responses_never_carry_raw_identity_or_network_fields(client, analyst, data):
    import hashlib

    full_sha = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    with TestingSessionLocal() as session:
        fingerprints = [s.analysis_fingerprint for s in session.scalars(select(InstrumentResultSet))]
    texts = [
        client.get("/api/instrument-results", params=RANGE, headers=analyst).text,
        *(client.get(f"/api/instrument-results/{id_set}", headers=analyst).text for id_set in data["sets"].values() if id_set),
    ]
    for text_body in texts:
        assert "PNG&R&" not in text_body and full_sha not in text_body
        assert not any(fingerprint in text_body for fingerprint in fingerprints)
        for forbidden_key in (
            "raw_bytes", "raw_message", "raw_sha256\"", "analysis_fingerprint", "p5_populated", "p8_populated",
            "test_code_qualifier", "source_offset", "source_record_index", "peer_", "local_", "error_detail",
            "nomor_rm", "no_registrasi", "nama_lengkap", "id_pasien", "id_visit", "id_order", "id_run", "waktu_run",
        ):
            assert forbidden_key not in text_body, forbidden_key
        json.loads(text_body)


def test_reads_write_no_audit_rows_and_create_no_clinical_rows(client, analyst, data):
    client.get("/api/instrument-results", params=RANGE, headers=analyst)
    client.get(f"/api/instrument-results/{data['sets']['a']}", headers=analyst)
    with TestingSessionLocal() as session:
        for model in (AuditEvent, Patient, Visit, Order, ClinicalRun, Result):
            assert session.scalar(select(func.count()).select_from(model)) == 0, model.__tablename__


def test_instrument_status_normalises_listening(client, analyst, data):
    with TestingSessionLocal() as session:
        session.get(Instrument, data["xn"]).connection_status = "LISTENING"
        session.get(Instrument, data["bc"]).connection_status = "SOMETHING_ELSE"
        session.commit()
    statuses = {row["id_instrument"]: row["connection_status"] for row in client.get("/api/instruments/status", headers=analyst).json()}
    assert statuses[data["xn"]] == "LISTENING"
    assert statuses[data["bc"]] == "UNKNOWN"


# --------------------------------------------------------------------------- #
# Import guard: no clinical model, schema or repository (§12.3, B.5)
# --------------------------------------------------------------------------- #

GUARDED_MODULES = (
    "app/api/routers/instrument_results.py",
    "app/schemas/instrument_results.py",
    "app/services/instrument_result_service.py",
    "app/integration/xn550_observations.py",
    "app/integration/xn550_normalize.py",
    "app/integration/xn550_ingestion.py",
    "app/models/instrument_result_set.py",
    "app/models/instrument_result_item.py",
)
FORBIDDEN_MODULES = {
    "app.models.patient", "app.models.visit", "app.models.order", "app.models.test_run", "app.models.result",
    "app.schemas.clinical", "app.schemas.overview", "app.schemas.test_run", "app.integration.repository",
    "app.services.overview_service", "app.services.test_run_service",
}
FORBIDDEN_NAMES = {"Patient", "Visit", "Order", "TestRun", "Result", "User", "AuditEvent"}


@pytest.mark.parametrize("relative_path", GUARDED_MODULES)
def test_xn550_observation_modules_import_nothing_clinical(relative_path):
    tree = ast.parse((BACKEND / relative_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name for alias in node.names} & FORBIDDEN_MODULES
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in FORBIDDEN_MODULES, node.module
            assert not {alias.name for alias in node.names} & FORBIDDEN_NAMES, (node.module, [a.name for a in node.names])


# --------------------------------------------------------------------------- #
# Development end-to-end: the API response the React views actually consume
# --------------------------------------------------------------------------- #

FRONTEND_TYPES = BACKEND.parent / "frontend" / "src" / "types" / "api.ts"
TYPE_OF_PAYLOAD = {
    "InstrumentResultSetSummary": ("list", "items"),
    "PaginatedInstrumentResultSetResponse": ("list", None),
    "InstrumentResultSetDetail": ("detail", None),
    "InstrumentResultItemResponse": ("detail", "items"),
    "InstrumentResultDeliveryResponse": ("detail", "deliveries"),
    "InstrumentResultProvenanceResponse": ("detail", "provenance"),
}


def _declared_fields(interface: str) -> set:
    source = FRONTEND_TYPES.read_text(encoding="utf-8")
    start = source.index(f"export interface {interface} {{")
    body = source[start:source.index("\n}", start)]
    return {
        line.strip().split(":")[0].rstrip("?")
        for line in body.splitlines()[1:]
        if line.strip() and not line.strip().startswith("//")
    }


@pytest.mark.parametrize("interface", sorted(TYPE_OF_PAYLOAD))
def test_api_payload_matches_the_frontend_types_field_for_field(client, analyst, data, interface):
    """The React views mirror these shapes by hand; nothing else would catch a rename."""
    listing = client.get("/api/instrument-results", params=RANGE, headers=analyst)
    detail = client.get(f"/api/instrument-results/{data['sets']['a']}", headers=analyst)
    assert listing.status_code == 200 and detail.status_code == 200, (listing.text, detail.text)
    payloads = {"list": listing.json(), "detail": detail.json()}

    endpoint, member = TYPE_OF_PAYLOAD[interface]
    payload = payloads[endpoint]
    if member is not None:
        value = payload[member]
        payload = value[0] if isinstance(value, list) else value
        assert payload, f"{interface}: the fixture produced no {member} to compare"

    assert set(payload) == _declared_fields(interface), interface
