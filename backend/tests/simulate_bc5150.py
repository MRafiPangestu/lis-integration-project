import socket
import time
import argparse
import re

HL7_SAMPLE_NORMAL = (
    "MSH|^~\\&|||||20260901145257||ORU^R01|{control_id}|P|2.3.1||||||UNICODE\r"
    "PID|1||^^^^MR||^supartini|||Female\r"
    "PV1|1\r"
    "OBR|1||{obr3}|00001^Automated Count^99MRC|||{obr7}|||||||||||||||||HM||||||||Administrator\r"
    "OBX|1|IS|08001^Take Mode^99MRC||O||||||F\r"
    "OBX|2|NM|6690-2^WBC^LN||18.40|10*3/uL|4.00-10.00|H~N|||F\r"
    "OBX|3|NM|718-7^HGB^LN||12.8|g/dL|11.0-16.0|N|||F\r"
    "OBX|4|IS|12002^Leucocytosis^99MRC||T||||||F\r"
)

HL7_SAMPLE_MISSING_MSH10 = (
    "MSH|^~\\&|||||20260901145257||ORU^R01||P|2.3.1||||||UNICODE\r"
    "PID|1||^^^^MR||^supartini|||Female\r"
    "PV1|1\r"
    "OBR|1||30|00001^Automated Count^99MRC|||20230519094058|||||||||||||||||HM||||||||Administrator\r"
    "OBX|1|NM|6690-2^WBC^LN||18.40|10*3/uL|4.00-10.00|H~N|||F\r"
)

def build_msg(control_id, obr3, obr7):
    return HL7_SAMPLE_NORMAL.format(control_id=control_id, obr3=obr3, obr7=obr7)

def send_mllp(conn, text):
    msg = b'\x0b' + text.encode('utf-8') + b'\x1c\x0d'
    conn.sendall(msg)

def wait_for_ack(conn, expected_control_id=None):
    conn.settimeout(10.0)
    try:
        data = conn.recv(1024)
        print(f"Received ACK bytes: {data}")
        # parse MLLP ACK
        decoded = data.decode('utf-8', errors='ignore')
        
        # extract MSA.1 and MSA.2
        msa_match = re.search(r'MSA\|([A-Z]{2})\|([^|^\r]+)', decoded)
        if not msa_match:
            print("Failed to parse MSA segment")
            return False, None
            
        msa_code = msa_match.group(1)
        msa_control_id = msa_match.group(2)
        
        if expected_control_id and msa_control_id != expected_control_id:
            print(f"Mismatch Control ID! Expected: {expected_control_id}, Got: {msa_control_id}")
            return False, None
            
        return True, msa_code
    except socket.timeout:
        print("Timeout waiting for ACK")
        return False, None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["normal", "missing_obr7", "missing_obr3", "missing_both", "missing_msh10", "split", "multi", "mass_retran"], default="mass_retran")
    args = parser.parse_args()

    host = '127.0.0.1'
    port = 5100

    print(f"Starting simulator on {host}:{port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        
        while True:
            print("Waiting for LIS connection...")
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                time.sleep(1)
                
                if args.mode == "mass_retran":
                    frames_sent = 0
                    ack_aa = 0
                    ack_ae = 0
                    missing_ack = 0
                    for m in range(1001, 1011):
                        for t in range(1, 5):
                            msg_id = f"M{m}T{t}"
                            obr3 = str(m)
                            obr7 = f"202305190940{str(m-1000).zfill(2)}"
                            
                            msg = build_msg(msg_id, obr3, obr7)
                            send_mllp(conn, msg)
                            frames_sent += 1
                            
                            success, code = wait_for_ack(conn, expected_control_id=msg_id)
                            if success:
                                if code == "AA": ack_aa += 1
                                elif code == "AE": ack_ae += 1
                            else:
                                missing_ack += 1
                            time.sleep(0.05)
                    
                    print(f"\nTotal frames sent: {frames_sent}")
                    print(f"actual_ACK_AA_received: {ack_aa}")
                    print(f"actual_ACK_AE_received: {ack_ae}")
                    print(f"missing_ACK: {missing_ack}")
                    
                elif args.mode == "missing_msh10":
                    send_mllp(conn, HL7_SAMPLE_MISSING_MSH10)
                    success, code = wait_for_ack(conn)
                    if success:
                        print(f"ACK received: {code}")
                    else:
                        print("No ACK received (Expected for missing MSH.10).")

                elif args.mode == "normal":
                    send_mllp(conn, build_msg("NORM1", "30", "20230519094058"))
                    wait_for_ack(conn, "NORM1")

                elif args.mode == "missing_obr7":
                    send_mllp(conn, build_msg("ERR1", "30", ""))
                    wait_for_ack(conn, "ERR1")
                    
                elif args.mode == "missing_obr3":
                    send_mllp(conn, build_msg("ERR2", "", "20230519094058"))
                    wait_for_ack(conn, "ERR2")
                    
                elif args.mode == "missing_both":
                    send_mllp(conn, build_msg("ERR3", "", ""))
                    wait_for_ack(conn, "ERR3")
                    
                elif args.mode == "split":
                    msg = build_msg("SPLIT1", "40", "20230519094058")
                    raw = b'\x0b' + msg.encode('utf-8') + b'\x1c\x0d'
                    conn.sendall(raw[:50])
                    time.sleep(1)
                    conn.sendall(raw[50:])
                    wait_for_ack(conn, "SPLIT1")

                elif args.mode == "multi":
                    msg1 = build_msg("MULTI1", "50", "20230519094058")
                    msg2 = build_msg("MULTI2", "60", "20230519094058")
                    raw = (b'\x0b' + msg1.encode('utf-8') + b'\x1c\x0d') + (b'\x0b' + msg2.encode('utf-8') + b'\x1c\x0d')
                    conn.sendall(raw)
                    wait_for_ack(conn, "MULTI1")
                    wait_for_ack(conn, "MULTI2")

                break

if __name__ == "__main__":
    main()
