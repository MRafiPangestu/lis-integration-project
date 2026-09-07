import socket
import time
import psycopg2
import sys
from psycopg2 import OperationalError
from hl7_parser import parse_hl7_message

# ==========================================
# KONFIGURASI JARINGAN & DATABASE
# ==========================================
MINDRAY_IP = '10.0.0.2'
MINDRAY_PORT = 5100

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "lis_marina_permata"
DB_USER = "postgres"
DB_PASS = "super-user"

def get_db_connection():
    """Membuka koneksi baru ke database untuk mencegah timeout saat idle berjam-jam."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        return conn
    except OperationalError as e:
        print(f"[!] Gagal terhubung ke database: {e}")
        return None

def save_hl7_to_db(raw_text, parsed_data):
    """Menyimpan data HL7 ke skema PostgreSQL menggunakan psycopg2"""
    db_conn = get_db_connection()
    if not db_conn:
        print("[-] Data gagal disimpan karena koneksi database terputus.")
        return

    cursor = db_conn.cursor()
    id_instrument = 2  # Set ID = 2 untuk Mindray BC-5150
    
    pat_data = parsed_data.get("patient", {})
    res_data = parsed_data.get("results", [])
    
    if not res_data:
        print("[-] Tidak ada data numerik untuk disimpan.")
        cursor.close()
        db_conn.close()
        return

    try:
        # 1. SIMPAN RAW MESSAGE (AUDIT TRAIL)
        cursor.execute(
            "INSERT INTO instrument_messages (id_instrument, raw_message) VALUES (%s, %s) RETURNING id_message",
            (id_instrument, raw_text)
        )
        id_message = cursor.fetchone()[0]

        # 2. CEK / INSERT PASIEN
        nomor_rm = pat_data.get("nomor_rm", "UNKNOWN")
        nama_pasien = pat_data.get("nama_lengkap", "UNKNOWN")
        
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
            
        # 3. INSERT ORDER BARU
        cursor.execute(
            "INSERT INTO orders (id_pasien) VALUES (%s) RETURNING id_order",
            (id_pasien,)
        )
        current_order_id = cursor.fetchone()[0]
        
        print(f"\n   => [DB PASIEN] {nama_pasien} (RM: {nomor_rm}) | Order ID: {current_order_id}")

        # 4. UPSERT HASIL LAB (RESULTS)
        for res in res_data:
            test_name = res["parameter_tes"]
            nilai = res["nilai_hasil"]
            satuan = res["satuan"]
            flag = res["flag_abnormalitas"]
            ref_range = res["reference_range_snapshot"]
            
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
        print(f"   => [SUCCESS] {len(res_data)} parameter berhasil disimpan.")
        
    except Exception as e:
        db_conn.rollback()
        print(f"[!] Error DB Transaksi: {e}")
    finally:
        cursor.close()
        db_conn.close()

# ==========================================
# FUNGSI SERVER UTAMA (MODE CLIENT HL7)
# ==========================================
def lis_client_hl7():
    print("[*] LIS Server (HL7 Client) mulai berjalan...")
    
    while True:
        try:
            print(f"\n[*] Mencoba menghubungi Mindray di {MINDRAY_IP}:{MINDRAY_PORT}...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5.0) 
                s.connect((MINDRAY_IP, MINDRAY_PORT))
                print("[+] Tersambung ke alat Mindray! Sistem standby menerima data...")
                
                s.settimeout(None) 
                buffer_data = ""
                
                while True:
                    data = s.recv(4096)
                    if not data:
                        print("[-] Koneksi ditutup oleh mesin Mindray.")
                        break
                    
                    if len(data) == 1 and data == b'\x02':
                        continue
                    
                    buffer_data += data.decode('utf-8', errors='ignore')
                    
                    # LOGIKA BATCH TRANSMISSION: Memecah antrean data pasien berdasarkan karakter \x1c
                    while '\x1c' in buffer_data:
                        pesan_utuh, sisa_antrean = buffer_data.split('\x1c', 1)
                        print("\n[*] Paket HL7 utuh diterima. Memproses...")
                        
                        parsed_data = parse_hl7_message(pesan_utuh)
                        save_hl7_to_db(pesan_utuh, parsed_data)
                        
                        buffer_data = sisa_antrean 
                        
        except ConnectionRefusedError:
            print("[-] Koneksi ditolak. Mesin mungkin sedang mati atau kabel tercabut.")
        except TimeoutError:
            print("[-] Timeout jaringan. Tidak dapat menemukan IP mesin.")
        except ConnectionResetError:
            print("[!] Koneksi diputus paksa oleh mesin (Connection Reset).")
        except KeyboardInterrupt:
            print("\n[*] LIS Server dimatikan secara manual. Sampai jumpa!")
            sys.exit(0)
        except Exception as e:
            print(f"[!] Error jaringan tidak terduga: {e}")
            
        print("[*] Mencoba menyambung kembali dalam 5 detik...")
        time.sleep(5)

if __name__ == '__main__':
    lis_client_hl7()