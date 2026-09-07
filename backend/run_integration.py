"""Integration-service entrypoint.

Instrument connectivity is read from the per-instrument configuration contract
(`backend/instruments.json`, see `instruments.example.json`). This entrypoint
binds each enabled instrument to its parser and database identity and hands the
worker set to the supervisor, which detects worker-thread death, restarts it,
and runs a deterministic shutdown. The dynamic parser registry is M8.3.
"""
import signal
import sys
import threading

from app.core.database import SessionLocal
from app.integration.client import InstrumentClient
from app.integration.instruments import (
    InstrumentConfigError,
    RuntimeInstrument,
    load_runtime_instruments,
)
from app.integration.parsers.hl7 import parse_hl7_bc5150
from app.integration.repository import process_message
from app.integration.supervisor import Supervisor

# Minimal parser binding for M8.1. Dynamic, config-driven parser selection is M8.3.
_PARSERS = {
    "bc5150_hl7": parse_hl7_bc5150,
}


def resolve_parser(parser_key: str):
    try:
        return _PARSERS[parser_key]
    except KeyError:
        raise InstrumentConfigError(
            f"No parser bound for parser_key {parser_key!r}. "
            f"Known parser keys: {sorted(_PARSERS)}."
        )


def make_handler(runtime: RuntimeInstrument, parser):
    def on_message(raw_frame: bytes, transport):
        with SessionLocal() as session:
            process_message(
                raw_frame,
                transport,
                runtime.id_instrument,
                session,
                parser=parser,
                identity_prefix=runtime.config.identity_prefix,
            )

    return on_message


def make_signal_handler(shutdown_event: threading.Event):
    """SIGINT handler: set the shutdown flag and return. No I/O, no sys.exit —
    the supervisor owns the shutdown sequence."""

    def _handler(signum, frame):
        shutdown_event.set()

    return _handler


def worker_factory(runtime: RuntimeInstrument):
    """Build a fresh (client, unstarted thread) pair for one instrument.

    Called at startup and again by the supervisor on every restart. It never
    re-reads instruments.json — it works only from the given RuntimeInstrument.
    """
    parser = resolve_parser(runtime.config.parser_key)
    client = InstrumentClient(
        runtime.config.host, runtime.config.port, runtime.id_instrument
    )
    thread = threading.Thread(
        target=client.recv_loop,
        args=(make_handler(runtime, parser),),
        name=f"instrument-{runtime.config.key}",
    )
    return client, thread


def main() -> None:
    with SessionLocal() as session:
        runtimes = load_runtime_instruments(session)

    if not runtimes:
        print("[!] No enabled instruments in configuration.")
        print("    Copy backend/instruments.example.json to backend/instruments.json "
              "and enable an instrument.")
        sys.exit(1)

    # Fail fast on an unknown parser_key, before any worker or status write.
    for runtime in runtimes:
        resolve_parser(runtime.config.parser_key)

    shutdown_event = threading.Event()
    signal.signal(signal.SIGINT, make_signal_handler(shutdown_event))

    print(f"[*] Starting Integration Service for {len(runtimes)} instrument(s): "
          f"{', '.join(rt.config.key for rt in runtimes)}")

    Supervisor(
        runtimes,
        worker_factory,
        shutdown_event=shutdown_event,
    ).run()

    print("[*] Integration service stopped.")


if __name__ == "__main__":
    main()
