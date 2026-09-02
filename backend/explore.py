import socket
import time

MINDRAY_IP = "10.0.0.2"  # Sesuaikan dengan IP BC-5150 asli
MINDRAY_PORT = 5100      # Port HL7 utama

def scan_ports(ip, ports=[21, 22, 23, 80, 8080, 5100]):
    print(f"--- 1. Memindai Port Terbuka di {ip} ---")
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((ip, port))
            if result == 0:
                print(f"[+] Port {port} TERBUKA")
            s.close()
        except Exception:
            pass
    print("-" * 40 + "\n")

def send_payload(payload_name, payload_bytes):
    print(f"--- Eksekusi: {payload_name} ---")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3) # Tunggu respon maksimal 3 detik agar tidak menggantung
        s.connect((MINDRAY_IP, MINDRAY_PORT))
        print("[*] Terhubung ke mesin...")
        
        s.sendall(payload_bytes)
        print(f"[*] Payload {payload_name} terkirim. Menunggu respons...")
        
        response = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass # Timeout normal jika mesin diam dan tidak merespons
        
        if response:
            print(f"[+] Respons diterima ({len(response)} bytes):")
            print(response)
        else:
            print("[-] Tidak ada respons dari mesin.")
            
        s.close()
    except ConnectionRefusedError:
        print("[-] Koneksi ditolak. Mesin mungkin menolak koneksi atau sedang restart/crash.")
    except Exception as e:
        print(f"[-] Error: {e}")
    print("-" * 40 + "\n")

if __name__ == "__main__":
    print("Mulai Eksperimen Reverse-Engineering BC-5150...\n")
    
    # Eksperimen 1: Cek Port Tersembunyi (FTP/Telnet/Web)
    scan_ports(MINDRAY_IP)
    
    # Eksperimen 2: Empty MLLP Ping (Memancing flush buffer)
    mllp_ping = b"\x0b\x1c\x0d"
    send_payload("Empty MLLP Ping", mllp_ping)
    
    time.sleep(2)
    
    # Eksperimen 3: Dummy ACK (Berjaga-jaga jika mesin macet nunggu ACK)
    dummy_ack = b"\x0bMSH|^~\\&|LIS||BC-5150||20260902140000||ACK^R01|1|P|2.3.1|\rMSA|AA|0|\r\x1c\x0d"
    send_payload("Dummy ACK", dummy_ack)
    
    time.sleep(2)
    
    # Eksperimen 4: Dummy LIS Fetch / Worklist (ORM^O01)
    # Pura-pura mengirim order untuk sampel 1001 untuk memancing mesin membalas dengan hasil
    dummy_orm = b"\x0bMSH|^~\\&|LIS||BC-5150||20260902140000||ORM^O01|2|P|2.3.1|\rPID|1||^^^^MR||UNKNOWN|\rORC|NW|1001||||||||||||||\rOBR|1|1001||00001^Automated Count^99MRC|||20260902140000|||||||||||||||||HM||\r\x1c\x0d"
    send_payload("Dummy ORM^O01 (LIS Fetch)", dummy_orm)
    
    print("Eksperimen selesai. Silakan periksa layar mesin BC-5150, apakah normal atau crash/hang.")