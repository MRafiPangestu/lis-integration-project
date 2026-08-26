import socket
import time

ENQ = b'\x05'
EOT = b'\x04'

# --- DATA PASIEN 1 ---
SAMPEL_1 = [
    b"1H|\\^&|||Sysmex_XN-550|||||||P|1\r\n",
    b"2P|1||123456789||Doe^John||19800101|M\r\n",
    b"3R|1|^^^WBC|7.5|10^3/uL||N|||||F\r\n"
]

# --- DATA PASIEN 2 (Pasien Baru) ---
SAMPEL_2 = [
    b"1H|\\^&|||Sysmex_XN-550|||||||P|1\r\n",
    b"2P|1||987654321||Smith^Jane||19900505|F\r\n",
    b"3R|1|^^^WBC|12.1|10^3/uL||H|||||F\r\n",
    b"4R|2|^^^RBC|4.2|10^6/uL||N|||||F\r\n"
]

def kirim_data_ke_lis(data_pasien):
    HOST = '127.0.0.1'
    PORT = 5000
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        
        # Mesin minta izin (Handshake)
        s.sendall(ENQ)
        time.sleep(0.5) # Jeda agar terminal tidak terlalu cepat
        
        # Mesin mengirim baris data satu per satu
        for baris in data_pasien:
            s.sendall(baris)
            time.sleep(0.5)
            
        # Mesin pamit
        s.sendall(EOT)

def jalankan_batch_simulator():
    print("[*] Menyalakan Mesin Sysmex Simulator...\n")
    
    print("[>] Memproses Tabung Darah 1 (John Doe)...")
    kirim_data_ke_lis(SAMPEL_1)
    
    print("\n[*] Mesin sedang mencuci jarum (Jeda 3 detik)...")
    time.sleep(3)
    
    print("\n[>] Memproses Tabung Darah 2 (Jane Smith)...")
    kirim_data_ke_lis(SAMPEL_2)
    
    print("\n[*] Semua antrean sampel selesai dikerjakan.")

if __name__ == '__main__':
    jalankan_batch_simulator()