from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "dbname": "lis_marina_permata",
    "user": "postgres",
    "password": "super-user"
}

@app.get("/api/results")
def get_lab_results():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # WAJIB MEMUAT r.waktu_hasil agar sorting frontend tidak error
        cursor.execute("""
            SELECT 
                p.nomor_rm, 
                p.nama_lengkap, 
                o.waktu_order, 
                r.waktu_hasil,
                r.parameter_tes, 
                r.nilai_hasil, 
                r.satuan, 
                r.flag_abnormalitas, 
                r.status_hasil
            FROM results r
            JOIN orders o ON r.id_order = o.id_order
            JOIN patients p ON o.id_pasien = p.id_pasien
            ORDER BY r.waktu_hasil DESC
        """)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Konversi datetime menjadi string ISO
        for row in data:
            if row.get('waktu_order'):
                row['waktu_order'] = row['waktu_order'].isoformat()
            if row.get('waktu_hasil'):
                row['waktu_hasil'] = row['waktu_hasil'].isoformat()
            
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e), "data": []}