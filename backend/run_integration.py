import os
import signal
import sys
import threading
from app.core.config import settings
from app.core.database import SessionLocal
from app.integration.client import InstrumentClient
from app.integration.repository import process_message

MINDRAY_IP = os.getenv("MINDRAY_IP", "10.0.0.2")
MINDRAY_PORT = int(os.getenv("MINDRAY_PORT", "5100"))
MINDRAY_INSTRUMENT_ID = int(os.getenv("MINDRAY_INSTRUMENT_ID", "2"))

client = InstrumentClient(MINDRAY_IP, MINDRAY_PORT, MINDRAY_INSTRUMENT_ID)

def on_message(raw_frame: bytes, transport):
    with SessionLocal() as session:
        process_message(raw_frame, transport, MINDRAY_INSTRUMENT_ID, session)

def signal_handler(sig, frame):
    print("\n[*] Shutting down integration service...")
    client.stop()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    print(f"[*] Starting Integration Service for instrument {MINDRAY_INSTRUMENT_ID}")
    
    thread = threading.Thread(target=client.recv_loop, args=(on_message,))
    thread.start()
    
    try:
        thread.join()
    except KeyboardInterrupt:
        signal_handler(None, None)

