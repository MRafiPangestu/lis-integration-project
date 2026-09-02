import datetime
from typing import Optional
from app.integration.parsers import ParsedHL7, ParsedPatient, ParsedOrder, ParsedResult

def parse_hl7_bc5150(raw_text: str) -> Optional[ParsedHL7]:
    segments = raw_text.split('\r')
    
    control_id = ""
    patient_id = ""
    patient_name = ""
    gender = None
    
    specimen_no = ""
    waktu_run = None
    
    results = []
    
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
            
        fields = segment.split('|')
        seg_type = fields[0]
        
        if seg_type == 'MSH':
            if len(fields) > 9:
                control_id = fields[9]
                
        elif seg_type == 'PID':
            # PID.3 is field 3
            if len(fields) > 3:
                pid3 = fields[3]
                sub_fields = pid3.split('^')
                if sub_fields:
                    patient_id = sub_fields[0].strip()
            
            if len(fields) > 5:
                # Name
                patient_name_parts = fields[5].split('^')
                patient_name = " ".join([p.strip() for p in patient_name_parts if p.strip()])
                
            if len(fields) > 8:
                raw_gender = fields[8].strip().lower()
                if raw_gender == 'female' or raw_gender == 'f':
                    gender = 'F'
                elif raw_gender == 'male' or raw_gender == 'm':
                    gender = 'M'
                    
        elif seg_type == 'OBR':
            if len(fields) > 3:
                specimen_no = fields[3].strip()
            if len(fields) > 7:
                dt_str = fields[7].strip()
                if len(dt_str) >= 14:
                    try:
                        waktu_run = datetime.datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
                    except ValueError:
                        pass
                        
        elif seg_type == 'OBX':
            if len(fields) > 5:
                data_type = fields[2].strip()
                if data_type not in ('NM', 'ST'):
                    continue
                
                # Check keywords as backup
                param_raw = fields[3]
                param_upper = param_raw.upper()
                if 'HISTOGRAM' in param_upper or 'SCATTERGRAM' in param_upper or 'BASE64' in param_upper:
                    continue
                    
                param_parts = param_raw.split('^')
                param_name = param_parts[1] if len(param_parts) > 1 else param_raw
                
                nilai = fields[5].strip()
                satuan = fields[6].strip() if len(fields) > 6 else None
                ref_range = fields[7].strip() if len(fields) > 7 else None
                
                flag = None
                if len(fields) > 8:
                    flag_raw = fields[8].strip()
                    if flag_raw:
                        flag_parts = flag_raw.split('~')
                        flag = flag_parts[0] if flag_parts else flag_raw
                        if not flag or flag == 'N':
                            flag = None
                
                if not nilai:
                    continue
                    
                results.append(ParsedResult(
                    parameter_tes=param_name,
                    nilai_hasil=nilai,
                    satuan=satuan,
                    flag_abnormalitas=flag,
                    reference_range_snapshot=ref_range
                ))
                
    if not control_id:
        return None
        
    return ParsedHL7(
        control_id=control_id,
        patient=ParsedPatient(
            nomor_rm=patient_id,
            nama_lengkap=patient_name or "UNKNOWN",
            jenis_kelamin=gender
        ),
        order=ParsedOrder(
            specimen_no=specimen_no,
            waktu_run=waktu_run
        ),
        results=results
    )

