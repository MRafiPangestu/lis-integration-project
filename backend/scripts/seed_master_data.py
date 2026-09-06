import sys
from pathlib import Path

# Add backend directory to PYTHONPATH so imports work
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Instrument, Unit, TestGroup

# 1. DATABASE SAFETY CHECK
if settings.DB_NAME != "lis_marina_permata_dev":
    print(f"ABORT: Active database is '{settings.DB_NAME}'.")
    print("Seed process is STRICTLY limited to 'lis_marina_permata_dev'.")
    sys.exit(1)

INSTRUMENTS = [
    {"nama_mesin": "Mindray BC-5150", "protokol": "HL7", "tipe_koneksi": "TCP/IP"},
    {"nama_mesin": "Sysmex XN-550", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "Mindray BS-200E", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "Sysmex BX-3010", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "Boditech Med Inc. — ichroma II", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "Medica — EasyLyte PLUS", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "DFI — R-300", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "ACON / Mission — Insight Expert U120", "protokol": None, "tipe_koneksi": None},
    {"nama_mesin": "Precil — 106-AC-57000131 (Reported ID)", "protokol": None, "tipe_koneksi": None}
]

UNITS = [
    {"kode_unit": "IGD", "nama_unit": "IGD"},
    {"kode_unit": "IRJA", "nama_unit": "IRJA"},
    {"kode_unit": "IRNA", "nama_unit": "IRNA"},
    {"kode_unit": "ICU", "nama_unit": "ICU"},
    {"kode_unit": "NICU", "nama_unit": "NICU"},
    {"kode_unit": "PICU", "nama_unit": "PICU"},
    {"kode_unit": "PONEK", "nama_unit": "PONEK"},
    {"kode_unit": "VK", "nama_unit": "VK"},
    {"kode_unit": "MCU", "nama_unit": "MCU"},
    {"kode_unit": "APS", "nama_unit": "APS"}
]

TEST_GROUPS = [
    {"nama_group": "Hematologi", "urutan_tampil": 1},
    {"nama_group": "Urine", "urutan_tampil": 2},
    {"nama_group": "Feses", "urutan_tampil": 3},
    {"nama_group": "Kimia Darah", "urutan_tampil": 4},
    {"nama_group": "Imunoserologi", "urutan_tampil": 5},
    {"nama_group": "Lain-lain", "urutan_tampil": 6}
]

def seed_instruments(session: Session) -> dict:
    stats = {"inserted": 0, "existing": 0, "updated": 0, "skipped": 0}
    for data in INSTRUMENTS:
        existing = session.scalar(select(Instrument).where(Instrument.nama_mesin == data["nama_mesin"]))
        if not existing:
            new_instrument = Instrument(
                nama_mesin=data["nama_mesin"],
                protokol=data["protokol"],
                tipe_koneksi=data["tipe_koneksi"]
            )
            session.add(new_instrument)
            stats["inserted"] += 1
        else:
            # Controlled enrichment for BC-5150
            if data["nama_mesin"] == "Mindray BC-5150":
                updated = False
                if existing.protokol is None and data["protokol"] is not None:
                    existing.protokol = data["protokol"]
                    updated = True
                if existing.tipe_koneksi is None and data["tipe_koneksi"] is not None:
                    existing.tipe_koneksi = data["tipe_koneksi"]
                    updated = True
                
                if updated:
                    stats["updated"] += 1
                else:
                    stats["existing"] += 1
            else:
                stats["existing"] += 1
    return stats

def seed_units(session: Session) -> dict:
    stats = {"inserted": 0, "existing": 0, "updated": 0, "skipped": 0}
    for data in UNITS:
        existing = session.scalar(select(Unit).where(Unit.kode_unit == data["kode_unit"]))
        if not existing:
            new_unit = Unit(
                kode_unit=data["kode_unit"],
                nama_unit=data["nama_unit"]
            )
            session.add(new_unit)
            stats["inserted"] += 1
        else:
            stats["existing"] += 1
    return stats

def seed_test_groups(session: Session) -> dict:
    stats = {"inserted": 0, "existing": 0, "updated": 0, "skipped": 0}
    for data in TEST_GROUPS:
        existing = session.scalar(select(TestGroup).where(TestGroup.nama_group == data["nama_group"]))
        if not existing:
            new_group = TestGroup(
                nama_group=data["nama_group"],
                urutan_tampil=data["urutan_tampil"]
            )
            session.add(new_group)
            stats["inserted"] += 1
        else:
            stats["existing"] += 1
    return stats

def main():
    print("Resolving active DB...")
    print(f"Target Database: {settings.DB_NAME}")
    
    session = SessionLocal()
    try:
        print("Begin transaction...")
        inst_stats = seed_instruments(session)
        unit_stats = seed_units(session)
        group_stats = seed_test_groups(session)
        
        session.commit()
        print("Commit successful.\n")
        
        print("--- SEED RESULT ---")
        print("Instruments:")
        for k, v in inst_stats.items(): print(f"  {k.capitalize()}: {v}")
        print("Units:")
        for k, v in unit_stats.items(): print(f"  {k.capitalize()}: {v}")
        print("Test Groups:")
        for k, v in group_stats.items(): print(f"  {k.capitalize()}: {v}")
        
    except Exception as e:
        session.rollback()
        print("ABORT: Exception occurred during seed.")
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()

