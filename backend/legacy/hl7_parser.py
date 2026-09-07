# backend/hl7_parser.py

def parse_hl7_message(hl7_text):
    """
    Mengubah teks mentah HL7 dari Mindray BC-5150 menjadi struktur dictionary.
    Mengabaikan data grafik/Base64 dan hanya mengambil angka tes darah.
    """
    
    # Menyiapkan kerangka data kosong
    parsed_data = {
        "patient": {
            "nomor_rm": "UNKNOWN",
            "nama_lengkap": "UNKNOWN",
            "jenis_kelamin": "U"
        },
        "order": {
            "no_order": "UNKNOWN",
            "waktu_order": None
        },
        "results": []
    }

    # Memecah teks besar menjadi baris-baris berdasarkan karakter Enter (\r atau \n)
    # HL7 biasanya menggunakan \r (Carriage Return)
    segments = hl7_text.replace('\n', '\r').split('\r')

    for segment in segments:
        fields = segment.split('|')
        
        # Abaikan baris kosong
        if not fields or fields[0] == '':
            continue
            
        seg_type = fields[0]
        
        # 1. Menangkap Data Pasien
        if seg_type == 'PID':
            # Contoh: PID|1||^^^^MR||^supartini|||Female
            if len(fields) > 3 and fields[3]:
                # Ambil ID, hilangkan karakter ^ jika ada
                rm = fields[3].replace('^', '').strip()
                if rm:
                    parsed_data["patient"]["nomor_rm"] = rm
            
            if len(fields) > 5 and fields[5]:
                # Ambil Nama, ganti ^ menjadi spasi
                parsed_data["patient"]["nama_lengkap"] = fields[5].replace('^', ' ').strip()
                
            if len(fields) > 8 and fields[8]:
                parsed_data["patient"]["jenis_kelamin"] = fields[8]
                
        # 2. Menangkap Data Order/Pesanan
        elif seg_type == 'OBR':
            # Contoh: OBR|1||30|00001^Automated Count^99MRC|||20230519094058
            if len(fields) > 3 and fields[3]:
                parsed_data["order"]["no_order"] = fields[3]
            
            if len(fields) > 7 and fields[7]:
                parsed_data["order"]["waktu_order"] = fields[7]
                
        # 3. Menangkap Hasil Laboratorium
        elif seg_type == 'OBX':
            # Contoh: OBX|5|NM|6690-2^WBC^LN||18.40|10*3/uL|4.00-10.00|H~N|||F
            if len(fields) < 6:
                continue
            
            # Kita filter tipe data. 'IS' biasanya pengaturan mesin, kita butuh 'NM' (Numeric)
            data_type = fields[2]
            if data_type not in ['NM', 'ST']:
                continue
                
            test_info = fields[3]
            
            # Filter keras untuk membuang baris berisi grafik / Histogram
            if 'Histogram' in test_info or 'Scattergram' in test_info or 'Base64' in test_info:
                continue
                
            # Mengekstrak nama parameter (Misal: '6690-2^WBC^LN' -> 'WBC')
            test_parts = test_info.split('^')
            test_name = test_parts[1] if len(test_parts) > 1 else test_parts[0]
            
            value = fields[5].strip()
            # Jika mesin ngirim blank/bintang, kita lewati atau biarkan
            if not value or value == '*****':
                continue
                
            unit = fields[6].strip() if len(fields) > 6 else ""
            ref_range = fields[7].strip() if len(fields) > 7 else ""
            
            # Menangani Flag Abnormalitas (Misal: 'H~N' diambil 'H' nya saja)
            raw_flag = fields[8].strip() if len(fields) > 8 else ""
            flag = raw_flag.split('~')[0] if '~' in raw_flag else raw_flag
            if not flag or flag == 'N':
                flag = "N" # N = Normal
                
            parsed_data["results"].append({
                "parameter_tes": test_name,
                "nilai_hasil": value,
                "satuan": unit,
                "flag_abnormalitas": flag,
                "reference_range_snapshot": ref_range
            })

    return parsed_data

# ==========================================
# BLOK TESTING (Hanya jalan jika file ini dieksekusi langsung)
# ==========================================
if __name__ == "__main__":
    # Ini data Supartini dari log terminalmu
    sample_hl7 = r"""MSH|^~\&|||||20260827143137||ORU^R01|8|P|2.3.1||||||UNICODE
PID|1||^^^^MR||^supartini|||Female
PV1|1
OBR|1||30|00001^Automated Count^99MRC|||20230519094058|||||||||||||||||HM||||||||Administrator
OBX|1|IS|08001^Take Mode^99MRC||O||||||F
OBX|5|NM|6690-2^WBC^LN||18.40|10*3/uL|4.00-10.00|H~N|||F
OBX|16|NM|789-8^RBC^LN||4.75|10*6/uL|3.50-5.50|N|||F
OBX|17|NM|718-7^HGB^LN||12.8|g/dL|11.0-16.0|N|||F"""

    hasil_parsing = parse_hl7_message(sample_hl7)
    
    import json
    print("HASIL PARSER HL7:")
    print(json.dumps(hasil_parsing, indent=4))