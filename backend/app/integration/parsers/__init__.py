from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class ParsedPatient:
    nomor_rm: str
    nama_lengkap: str
    jenis_kelamin: Optional[str]

@dataclass
class ParsedOrder:
    specimen_no: str
    waktu_run: Optional[datetime]

@dataclass
class ParsedResult:
    parameter_tes: str
    nilai_hasil: str
    satuan: Optional[str]
    flag_abnormalitas: Optional[str]
    reference_range_snapshot: Optional[str]

@dataclass
class ParsedHL7:
    control_id: str
    patient: ParsedPatient
    order: ParsedOrder
    results: List[ParsedResult] = field(default_factory=list)

