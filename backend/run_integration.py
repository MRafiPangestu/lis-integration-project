"""Integration-service entrypoint.

Instrument connectivity is read from the per-instrument configuration contract
(`backend/instruments.json`, see `instruments.example.json`). This entrypoint
binds each enabled instrument to its database identity and hands the worker set
to the supervisor, which detects worker-thread death, restarts it, and runs a
deterministic shutdown.

* ``client`` mode (the LIS dials the instrument): bound to its parser via the
  M8.3 parser registry — unchanged.
* ``listener`` mode (the instrument dials the LIS): XN-550 Phase 1 G1 raw
  capture only (docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md
  §19.4). No parser is resolved, because none is registered for it.
"""
import functools
import signal
import sys
import threading

from app.core.config import ensure_unique_listener_bindings
from app.core.database import SessionLocal
from app.integration import classification
from app.integration.client import InstrumentClient
from app.integration.instruments import (
    RuntimeInstrument,
    load_runtime_instruments,
    write_instrument_status,
)
from app.integration.listener import build_listener_worker
from app.integration.parsers.registry import resolve_parser
from app.integration.raw_capture import SqlRawCaptureStore
from app.integration.repository import process_message
from app.integration.supervisor import Supervisor


def make_handler(runtime: RuntimeInstrument, parser, classify_fn):
    def on_message(raw_frame: bytes, transport):
        with SessionLocal() as session:
            process_message(
                raw_frame,
                transport,
                runtime.id_instrument,
                session,
                parser=parser,
                identity_prefix=runtime.config.identity_prefix,
                classify_fn=classify_fn,
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
    if runtime.config.mode == "listener":
        return build_listener_worker(
            runtime,
            store=SqlRawCaptureStore(SessionLocal),
            status_writer=write_instrument_status,
        )

    parser = resolve_parser(runtime.config.parser_key)
    policy = classification.resolve_policy(runtime.config.classification_policy)
    classify_fn = functools.partial(classification.classify, policy=policy)
    client = InstrumentClient(
        runtime.config.host, runtime.config.port, runtime.id_instrument
    )
    thread = threading.Thread(
        target=client.recv_loop,
        args=(make_handler(runtime, parser, classify_fn),),
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

    # Fail fast on an unregistered parser_key, before any worker or status write.
    # Listener-mode (G1 raw capture) instruments have no parser to resolve.
    for runtime in runtimes:
        if runtime.config.mode == "client":
            resolve_parser(runtime.config.parser_key)
    ensure_unique_listener_bindings(rt.config for rt in runtimes)

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
