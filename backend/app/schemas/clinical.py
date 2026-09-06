from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import List, Optional
from app.schemas.test_run import ResultResponse, TestRunResponse

class PatientResponse(BaseModel):
    id_pasien: int
    nomor_rm: str
    nama_lengkap: str
    tanggal_lahir: Optional[date] = None
    jenis_kelamin: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class VisitResponse(BaseModel):
    id_visit: int
    id_pasien: int
    no_registrasi: str
    waktu_kunjungan: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id_order: int
    id_visit: int
    id_unit: Optional[int] = None
    id_dokter: Optional[int] = None
    diagnosa: Optional[str] = None
    waktu_order: datetime
    status_order: str
    model_config = ConfigDict(from_attributes=True)

class InstrumentResponse(BaseModel):
    id_instrument: int
    nama_mesin: str
    protokol: Optional[str] = None
    tipe_koneksi: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class FlatResultResponse(ResultResponse):
    test_run: TestRunResponse
    instrument: Optional[InstrumentResponse] = None
    order: OrderResponse
    visit: VisitResponse
    patient: PatientResponse
    
    model_config = ConfigDict(from_attributes=True)

class PaginatedResultResponse(BaseModel):
    items: List[FlatResultResponse]
    page: int
    page_size: int
    total: int

# --- History Schemas ---

class HistoryResultResponse(ResultResponse):
    model_config = ConfigDict(from_attributes=True)

class HistoryTestRunResponse(TestRunResponse):
    instrument: Optional[InstrumentResponse] = None
    results: List[HistoryResultResponse] = []
    model_config = ConfigDict(from_attributes=True)

class HistoryOrderResponse(OrderResponse):
    test_runs: List[HistoryTestRunResponse] = []
    model_config = ConfigDict(from_attributes=True)

class HistoryVisitResponse(VisitResponse):
    orders: List[HistoryOrderResponse] = []
    model_config = ConfigDict(from_attributes=True)

class HistoryPatientResponse(PatientResponse):
    visits: List[HistoryVisitResponse] = []
    model_config = ConfigDict(from_attributes=True)

