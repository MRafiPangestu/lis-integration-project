from typing import Dict, Any
from app.models.test_run import TestRun

def build_simrs_payload(test_run: TestRun) -> Dict[str, Any]:
    """
    Constructs a TEMPORARY development payload representing the clinical hierarchy.
    This does NOT represent the final SIMRS production contract.
    It reads ORM data only and performs no mutations.
    """
    order = test_run.order
    visit = order.visit if order else None
    patient = visit.patient if visit else None

    payload = {
        "metadata": {
            "is_temporary_payload": True,
            "version": "1.0-dev"
        },
        "patient": {},
        "visit": {},
        "order": {},
        "test_run": {},
        "results": []
    }

    if patient:
        payload["patient"] = {
            "nomor_rm": patient.nomor_rm,
            "nama_lengkap": patient.nama_lengkap,
            "tanggal_lahir": patient.tanggal_lahir.isoformat() if patient.tanggal_lahir else None,
            "jenis_kelamin": patient.jenis_kelamin
        }

    if visit:
        payload["visit"] = {
            "no_registrasi": visit.no_registrasi
        }

    if order:
        payload["order"] = {
            "id_order": order.id_order,
            "diagnosa": order.diagnosa,
            "waktu_order": order.waktu_order.isoformat() if order.waktu_order else None
        }

    payload["test_run"] = {
        "id_run": test_run.id_run,
        "waktu_run": test_run.waktu_run.isoformat() if test_run.waktu_run else None,
        "is_final": test_run.is_final
    }

    if test_run.results:
        for res in test_run.results:
            payload["results"].append({
                "parameter_tes": res.parameter_tes,
                "nilai_hasil": res.nilai_hasil,
                "satuan": res.satuan,
                "flag_abnormalitas": res.flag_abnormalitas,
                "reference_range_snapshot": res.reference_range_snapshot
            })

    return payload
