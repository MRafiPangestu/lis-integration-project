from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional

class ResultResponse(BaseModel):
    id_hasil: int
    parameter_tes: str
    nilai_hasil: str
    satuan: Optional[str] = None
    flag_abnormalitas: Optional[str] = None
    reference_range_snapshot: Optional[str] = None
    waktu_hasil: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TestRunResponse(BaseModel):
    id_run: int
    id_order: int
    id_instrument: int
    run_sequence: int
    waktu_run: Optional[datetime] = None
    is_final: bool
    delivery_status: str
    delivered_at: Optional[datetime] = None
    created_at: datetime
    
    results: List[ResultResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

