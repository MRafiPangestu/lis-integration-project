import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Muat variabel dari file .env
load_dotenv()

# Inisialisasi Aplikasi FastAPI
app = FastAPI(title="LIS API Marina Permata", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Mengizinkan semua origin untuk tahap development
    allow_credentials=True,
    allow_methods=["*"], # Mengizinkan semua metode (GET, POST, dll)
    allow_headers=["*"], # Mengizinkan semua header
)

# Fungsi untuk membuka koneksi ke DB dengan Error Handling
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"[ERROR] Gagal terhubung ke Database: {e}")
        raise HTTPException(status_code=500, detail="Database Connection Error")

# ==========================================
# ENDPOINT (Jalur Akses Data)
# ==========================================

# 1. Endpoint Health Check
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API LIS menyala dan siap menerima perintah."}

# 2. Endpoint Mengambil Data Hasil Lab (Vertical Slice MVP)
@app.get("/api/results")
def get_all_results():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query yang mencerminkan relasi Skema Final kita
        query = """
            SELECT 
                p.nomor_rm,
                p.nama_lengkap,
                o.waktu_order,
                r.parameter_tes,
                r.nilai_hasil,
                r.satuan,
                r.flag_abnormalitas,
                r.reference_range_snapshot,
                r.status_hasil
            FROM results r
            JOIN orders o ON r.id_order = o.id_order
            JOIN patients p ON o.id_pasien = p.id_pasien
            ORDER BY r.waktu_hasil DESC;
        """
        
        cursor.execute(query)
        data = cursor.fetchall()
        
        return {"status": "success", "total_data": len(data), "data": data}
        
    except Exception as e:
        # Menangkap error jika query gagal (misal tabel tidak ditemukan)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
        
    finally:
        # Memastikan koneksi ditutup dengan aman meskipun terjadi error
        if conn:
            cursor.close()
            conn.close()