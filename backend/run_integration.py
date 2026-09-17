"""Integration-service entrypoint.

Instrument connectivity is read from the per-instrument configuration contract
(`backend/instruments.json`, see `instruments.example.json`). This entrypoint
binds each enabled instrument to its database identity and hands the worker set
to the supervisor, which detects worker-thread death, restarts it, and runs a
deterministic shutdown.

* ``client`` mode (the LIS dials the instrument): bound to its parser via the
  M8.3 parser registry — unchanged.
* ``listener`` mode (the instrument dials the LIS): XN-550 raw capture, envelope
  classification and byte-identity linking of each persisted raw message, plus
  unlinked observation sets when the entry's ``ingestion_stage`` is
  ``observations`` (G2)
  (docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md §19.4, §19.5,
  §19.8). Its parser is resolved through the same registry and must belong to
  the ASTM protocol family; no clinical rows are ever created.

Every parser key is checked against its registered protocol family at startup,
so an ASTM parser can never be bound to the HL7/MLLP client path or vice versa.
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
from app.integration.parsers.registry import (
    PROTOCOL_ASTM_E1394_CR,
    PROTOCOL_HL7_MLLP,
    ParserNotRegisteredError,
    protocol_family,
    resolve_parser,
)
from app.integration.parsers.xn550_astm import PARSER_VERSION as XN550_PARSER_VERSION
from app.integration.parsers.xn550_astm import resolve_xn550_policy
from app.integration.raw_capture import SqlRawCaptureStore
from app.integration.repository import process_message
from app.integration.supervisor import Supervisor
from app.integration.xn550_ingestion import Xn550ClassificationStage

# Protocol family each transport mode requires of its parser (contract §19.1).
_MODE_PROTOCOL_FAMILY = {"client": PROTOCOL_HL7_MLLP, "listener": PROTOCOL_ASTM_E1394_CR}


def resolve_runtime_parser(runtime: RuntimeInstrument):
    """Resolve the configured parser and refuse a protocol-family mismatch.

    Exact-match registry lookup (unknown key -> ParserNotRegisteredError, no
    fallback), then the key's registered family must match the transport mode.
    """
    key = runtime.config.parser_key
    parser = resolve_parser(key)
    family = protocol_family(key)
    required = _MODE_PROTOCOL_FAMILY[runtime.config.mode]
    if family != required:
        raise ParserNotRegisteredError(
            f"parser_key {key!r} is a {family} parser; instrument {runtime.config.key!r} "
            f"in {runtime.config.mode!r} mode requires a {required} parser."
        )
    return parser


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
        stage = Xn550ClassificationStage(
            session_factory=SessionLocal,
            parser=resolve_runtime_parser(runtime),
            policy=resolve_xn550_policy(runtime.config.classification_policy),
            parser_key=runtime.config.parser_key,
            parser_version=XN550_PARSER_VERSION,
            ingestion_stage=runtime.config.ingestion_stage,
        )
        return build_listener_worker(
            runtime,
            store=SqlRawCaptureStore(SessionLocal),
            status_writer=write_instrument_status,
            on_raw_committed=stage.process,
            on_serve_start=functools.partial(stage.process_pending, runtime.id_instrument),
        )

    parser = resolve_runtime_parser(runtime)
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

    # Fail fast on an unregistered parser_key or a protocol-family mismatch,
    # before any worker or status write.
    for runtime in runtimes:
        resolve_runtime_parser(runtime)
        if runtime.config.mode == "listener":
            resolve_xn550_policy(runtime.config.classification_policy)
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
