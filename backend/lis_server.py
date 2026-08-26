import socket
import psycopg2

ACK = b'\x06' 
EOT = b'\x04' 

# ==========================================
# KONFIGURASI DATABASE
# ==========================================
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "lis_marina_permata"
DB_USER = "postgres"
DB_PASS = "super-user"

current_order_id = None 

# ==========================================
# FUNGSI PARSER & SIMPAN KE DATABASE
# ==========================================
def parse_astm_and_save(raw_bytes, db_conn):
    global current_order_id
    
    text_line = raw_bytes.decode('utf-8', errors='ignore').strip()
    if len(text_line) < 2:
        return

    cursor = db_conn.cursor()
    id_instrument = 1 # ID Sysmex XN-550
    
    # 1. SIMPAN RAW MESSAGE (AUDIT TRAIL)
    cursor.execute(
        "INSERT INTO instrument_messages (id_instrument, raw_message) VALUES (%s, %s) RETURNING id_message",
        (id_instrument, text_line)
    )
    id_message = cursor.fetchone()[0]
    db_conn.commit()

    # 2. PROSES PARSING
    fields = text_line.split('|')
    record_type = fields[0][-1] 
    
    # JIKA BARIS PASIEN (P)
    if record_type == 'P':
        nomor_rm = fields[3]
        nama_pasien = fields[5].replace('^', ' ')
        
        # Cek / Insert Pasien
        cursor.execute("SELECT id_pasien FROM patients WHERE nomor_rm = %s", (nomor_rm,))
        row = cursor.fetchone()
        
        if row:
            id_pasien = row[0]
        else:
            cursor.execute(
                "INSERT INTO patients (nomor_rm, nama_lengkap) VALUES (%s, %s) RETURNING id_pasien",
                (nomor_rm, nama_pasien)
            )
            id_pasien = cursor.fetchone()[0]
            
        # Insert Order Baru (Kolom lain seperti id_unit/dokter akan diisi NULL sementara oleh sistem)
        cursor.execute(
            "INSERT INTO orders (id_pasien) VALUES (%s) RETURNING id_order",
            (id_pasien,)
        )
        current_order_id = cursor.fetchone()[0]
        db_conn.commit()
        
        print(f"   => [DB PASIEN] {nama_pasien} (RM: {nomor_rm}) | Order ID: {current_order_id}")

    # JIKA BARIS HASIL LAB (R)
    elif record_type == 'R':
        if not current_order_id:
            return 
            
        test_name = fields[2].split('^')[-1]
        nilai = fields[3]
        satuan = fields[4]
        
        # Ekstraksi Reference Range (Nilai Rujukan) dari index ke-5 jika ada
        ref_range = fields[5].strip() if len(fields) > 5 and fields[5].strip() else None
        
        # Ekstraksi Flag Abnormalitas dari index ke-6
        flag = fields[6].strip() if len(fields) > 6 and fields[6].strip() else 'N'
        
        # 3. LOGIKA UPSERT KE SKEMA BARU
        cursor.execute(
            """
            INSERT INTO results (
                id_order, id_instrument, id_message, parameter_tes, 
                nilai_hasil, satuan, flag_abnormalitas, reference_range_snapshot
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_order, parameter_tes) 
            DO UPDATE SET 
                nilai_hasil = EXCLUDED.nilai_hasil,
                satuan = EXCLUDED.satuan,
                flag_abnormalitas = EXCLUDED.flag_abnormalitas,
                reference_range_snapshot = EXCLUDED.reference_range_snapshot,
                id_message = EXCLUDED.id_message,
                waktu_hasil = CURRENT_TIMESTAMP
            """,
            (current_order_id, id_instrument, id_message, test_name, nilai, satuan, flag, ref_range)
        )
        db_conn.commit()
        print(f"   => [DB HASIL] {test_name}: {nilai} {satuan} | Flag: {flag} | Rujukan: {ref_range}")
        
    cursor.close()

# ==========================================
# FUNGSI SERVER UTAMA
# ==========================================
def lis_server():
    HOST = '127.0.0.1'
    PORT = 5000
    
    print("[*] Menghubungkan ke PostgreSQL (Skema Final)...")
    db_conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    print("[+] Database Terhubung!")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"[*] LIS Server Siaga di {HOST}:{PORT}")
        
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"\n[+] Menerima koneksi dari: {addr}")
                while True:
                    try:
                        data = conn.recv(1024)
                        if not data:
                            break
                        
                        parse_astm_and_save(data, db_conn)
                        
                        if EOT in data:
                            conn.sendall(ACK)
                            print("\n[*] Transmisi Selesai.")
                            break
                            
                        conn.sendall(ACK)
                    except ConnectionResetError:
                        break

if __name__ == '__main__':
    lis_server()