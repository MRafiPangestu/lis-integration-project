import socket
import time
import threading
from datetime import datetime
from typing import Callable
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from app.integration.protocols import InstrumentTransport
from app.core.database import SessionLocal
from app.models.instrument import Instrument

class InstrumentClient(InstrumentTransport):
    def __init__(self, host: str, port: int, instrument_id: int):
        self.host = host
        self.port = port
        self.instrument_id = instrument_id
        self._socket = None
        self._send_lock = threading.Lock()
        self._stop_event = threading.Event()

    def _update_status(self, status: str) -> None:
        try:
            with SessionLocal() as session:
                # Use bulk update for transaction safety and efficiency
                stmt = update(Instrument).where(
                    Instrument.id_instrument == self.instrument_id
                ).values(
                    connection_status=status,
                    last_status_at=datetime.utcnow()
                )
                session.execute(stmt)
                session.commit()
        except SQLAlchemyError as e:
            print(f"[!] Failed to update status to {status}: {e}")

    def stop(self):
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close()
            except:
                pass

    def _build_ack_aa(self, control_id: str) -> bytes:
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        hl7 = (
            f"MSH|^~\\&|LIS|RSMARINA||MINDRAY|{now}||ACK^R01|ACK{now}|P|2.3.1\r"
            f"MSA|AA|{control_id}\r"
        )
        return b'\x0b' + hl7.encode('utf-8') + b'\x1c\x0d'

    def _build_ack_ae(self, control_id: str, error: str) -> bytes:
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        hl7 = (
            f"MSH|^~\\&|LIS|RSMARINA||MINDRAY|{now}||ACK^R01|ACK{now}|P|2.3.1\r"
            f"MSA|AE|{control_id}|{error[:50]}\r"
        )
        return b'\x0b' + hl7.encode('utf-8') + b'\x1c\x0d'

    def send_ack(self, control_id: str, success: bool = True, error: str = "") -> None:
        if not self._socket:
            return

        if success:
            ack_bytes = self._build_ack_aa(control_id)
        else:
            ack_bytes = self._build_ack_ae(control_id, error)

        with self._send_lock:
            try:
                self._socket.sendall(ack_bytes)
            except Exception as e:
                print(f"[!] Failed to send ACK: {e}")

    def send_command(self, command: bytes) -> None:
        raise NotImplementedError("Outbound commands not yet implemented.")

    def recv_loop(self, on_message: Callable[[bytes, InstrumentTransport], None]) -> None:
        MLLP_SB = 0x0B
        MLLP_END = b'\x1c\x0d'

        while not self._stop_event.is_set():
            print(f"[*] Connecting to {self.host}:{self.port}...")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5.0)
                try:
                    s.connect((self.host, self.port))
                    print(f"[+] Connected to instrument {self.instrument_id}.")
                    self._update_status("CONNECTED")

                    self._socket = s
                    s.settimeout(1.0) # short timeout to check stop event

                    buffer = b""

                    while not self._stop_event.is_set():
                        try:
                            data = s.recv(4096)
                            if not data:
                                print("[-] Connection closed by instrument.")
                                break

                            buffer += data

                            while MLLP_END in buffer:
                                end_pos = buffer.index(MLLP_END)
                                start_pos = 1 if len(buffer) > 0 and buffer[0] == MLLP_SB else 0
                                raw_frame = buffer[start_pos:end_pos]
                                buffer = buffer[end_pos + 2:]

                                on_message(raw_frame, self)

                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[!] Socket read error: {e}")
                            break

                except (ConnectionRefusedError, socket.timeout):
                    print("[-] Connection failed or timed out.")
                except Exception as e:
                    print(f"[!] Connection error: {e}")
                finally:
                    self._socket = None

            if not self._stop_event.is_set():
                print("[*] Reconnecting in 5 seconds...")
                self._update_status("RECONNECTING")
                time.sleep(5)

        # Loop ended gracefully or stop_event set
        self._update_status("DISCONNECTED")

