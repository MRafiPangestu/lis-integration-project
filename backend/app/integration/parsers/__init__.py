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
class ParsedObxMetadata:
    """Inert IS-typed OBX metadata, retained for future evidence-based
    classification (M8.2b). Never interpreted by the current pipeline."""
    obx_type: str          # "IS"
    identifier: str        # raw OBX-3, e.g. "08001^Take Mode^99MRC"
    value: str             # raw OBX-5

@dataclass
class ParsedHL7:
    control_id: str
    patient: ParsedPatient
    order: ParsedOrder
    results: List[ParsedResult] = field(default_factory=list)
    is_metadata: List[ParsedObxMetadata] = field(default_factory=list)
