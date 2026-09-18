"""DEVELOPMENT ONLY — synthetic Sysmex XN-550 ASTM sender.

This is a development tool, not an instrument driver. It exists so the
socket -> listener -> raw capture -> classification -> G2 observation -> API
-> frontend path can be exercised on a developer machine without an
instrument. It is **not** evidence of physical instrument behaviour and it
replaces no field validation: the authority for what the XN-550 does is
``docs/instruments/sysmex_xn550/`` and nothing here.

Transport (contract OD-XN-1, field-verified): the instrument **dials the LIS**,
so this simulator is a TCP *client* and the LIS listens. It emits bare-CR ASTM
records (``ASTM_CR_RECORDS``) and reads the single ``0x06`` acknowledgement the
listener writes per read. It never sends a NAK and never emits E1381 framing —
neither was observed in the tested configuration, and the contract forbids
simulating unverified behaviour.

Payloads are derived from the committed redacted fixture by mutation. No PHI
and no raw external evidence is embedded in this file.

Usage (from ``backend/``)::

    python tests/simulate_xn550.py --mode single
    python tests/simulate_xn550.py --mode fragmented --chunk-size 200
    python tests/simulate_xn550.py --mode multi --count 5
    python tests/simulate_xn550.py --mode retransmit
    python tests/simulate_xn550.py --mode same-fingerprint
    python tests/simulate_xn550.py --mode deviation
    python tests/simulate_xn550.py --mode close-mid-message
"""
from __future__ import annotations

import argparse
import pathlib
import socket
import time
from typing import Iterable, List, Sequence

ACK = 0x06
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"

# Fixture landmarks, so a mutation never depends on payload content.
_ORDER_RECORD = 3
_COMMENT_RECORD = 2
_SAMPLE_LABEL_COMPONENT = 2
_BASE_STAMP = "20260915023225"

MODES = (
    "single",
    "fragmented",
    "multi",
    "retransmit",
    "same-fingerprint",
    "deviation",
    "close-mid-message",
)


def load_fixture() -> bytes:
    """The committed, redacted conformant message."""
    return FIXTURE.read_bytes()


def variant(
    raw: bytes,
    *,
    stamp: str | None = None,
    label: str | None = None,
    shift_folder: bool = False,
    measured_flag: str | None = None,
) -> bytes:
    """Derive a synthetic message. Same mutations the G2 tests use.

    ``measured_flag`` rewrites the first measured result's ``R``-7 flag. Only a
    value the corpus actually contains is worth passing (``W`` and ``A`` occur
    there, README §8.2): the point is to exercise a flag whose meaning is
    UNKNOWN, which the committed fixture happens not to carry.
    """
    records = raw.decode("ascii").split("\r")
    if measured_flag is not None:
        index = next(i for i, record in enumerate(records) if record.startswith("R|1|"))
        fields = records[index].split("|")
        fields[6] = measured_flag
        records[index] = "|".join(fields)
    if stamp:
        records = [record.replace(_BASE_STAMP, stamp) for record in records]
    if label:
        order = records[_ORDER_RECORD].split("|")
        components = order[3].split("^")
        components[_SAMPLE_LABEL_COMPONENT] = label
        order[3] = "^".join(components)
        records[_ORDER_RECORD] = "|".join(order)
    if shift_folder:
        index = next(i for i, record in enumerate(records) if "PNG&R&" in record)
        folder = records[index].split("PNG&R&", 1)[1][:8]
        records[index] = records[index].replace(f"PNG&R&{folder}", f"PNG&R&{int(folder) + 1:08d}", 1)
    return "\r".join(records).encode("ascii")


def deviation(raw: bytes) -> bytes:
    """A message whose envelope deviates: a populated comment record.

    Classification records ``XN550_DEV_POPULATED_COMMENT`` and creates no
    observation, which is the point of the mode.
    """
    records = raw.decode("ascii").split("\r")
    records[_COMMENT_RECORD] = "C|1||SIMULATED DEVIATION"
    return "\r".join(records).encode("ascii")


def chunks(payload: bytes, size: int) -> List[bytes]:
    return [payload[at:at + size] for at in range(0, len(payload), size)] or [b""]


def messages_for(mode: str, count: int, measured_flag: str | None = None) -> List[bytes]:
    """The payloads a mode sends, in order. Pure — no socket."""
    raw = load_fixture()
    if measured_flag is not None:
        raw = variant(raw, measured_flag=measured_flag)
    if mode in ("single", "fragmented", "close-mid-message"):
        return [raw]
    if mode == "retransmit":
        return [raw, raw]
    if mode == "same-fingerprint":
        return [raw, variant(raw, shift_folder=True)]
    if mode == "deviation":
        return [deviation(raw)]
    if mode == "multi":
        return [
            variant(raw, stamp=f"2026091504{index:02d}00", label=f"SIM-{index:04d}")
            for index in range(1, count + 1)
        ]
    raise ValueError(f"unknown mode: {mode}")


def writes_for(mode: str, payloads: Sequence[bytes], chunk_size: int) -> List[bytes]:
    """How those payloads are written to the socket, in order."""
    if mode == "fragmented":
        return chunks(payloads[0], chunk_size)
    if mode == "close-mid-message":
        # Everything up to the terminator: the listener records a fragment.
        body = payloads[0]
        cut = body.rfind(b"L|")
        return [body[:cut]]
    return list(payloads)


def send(
    writes: Iterable[bytes],
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    pause: float = 0.05,
    read_timeout: float = 5.0,
    verbose: bool = True,
) -> int:
    """Connect, write each chunk, read the acknowledgement, close. Returns ACK count."""
    acks = 0
    with socket.create_connection((host, port), timeout=read_timeout) as sock:
        sock.settimeout(read_timeout)
        if verbose:
            print(f"connected to {host}:{port} from {sock.getsockname()[1]}")
        for index, chunk in enumerate(writes, start=1):
            sock.sendall(chunk)
            if verbose:
                print(f"  write {index}: {len(chunk)} bytes")
            try:
                data = sock.recv(16)
            except socket.timeout:
                if verbose:
                    print("  no acknowledgement within the timeout")
                continue
            if data:
                assert set(data) == {ACK}, f"expected only 0x06, got {data!r}"
                acks += len(data)
                if verbose:
                    print(f"  ack: {len(data)} x 0x06")
            time.sleep(pause)
    if verbose:
        print(f"closed. acknowledgement bytes: {acks}")
    return acks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DEVELOPMENT ONLY synthetic XN-550 sender (not an instrument driver)",
    )
    parser.add_argument("--mode", choices=MODES, default="single")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--count", type=int, default=3, help="messages for --mode multi")
    parser.add_argument("--chunk-size", type=int, default=200, help="write size for --mode fragmented")
    parser.add_argument("--pause", type=float, default=0.05, help="seconds between writes")
    parser.add_argument(
        "--measured-flag",
        help="rewrite the first measured R-7 flag, e.g. W or A (corpus values whose meaning is UNKNOWN)",
    )
    args = parser.parse_args()

    print("DEVELOPMENT ONLY — synthetic payloads, not instrument evidence.")
    payloads = messages_for(args.mode, args.count, args.measured_flag)
    writes = writes_for(args.mode, payloads, args.chunk_size)
    print(f"mode={args.mode} payloads={len(payloads)} writes={len(writes)}")
    send(writes, host=args.host, port=args.port, pause=args.pause)


if __name__ == "__main__":
    main()
