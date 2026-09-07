"""Integration-service entrypoint.

Instrument connectivity is read from the per-instrument configuration contract
(`backend/instruments.json`, see `instruments.example.json`). This entrypoint
binds each enabled instrument to its parser and database identity and runs it on
its own thread. The full multi-instrument supervisor (restart policy, health,
lifecycle) is M8.1-B; the dynamic parser registry is M8.3.
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

# Minimal parser binding for M8.1-A. Dynamic, config-driven parser selection is M8.3.
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


def main() -> None:
    with SessionLocal() as session:
        runtimes = load_runtime_instruments(session)

    if not runtimes:
        print("[!] No enabled instruments in configuration.")
        print("    Copy backend/instruments.example.json to backend/instruments.json "
              "and enable an instrument.")
        sys.exit(1)

    clients: list[InstrumentClient] = []
    threads: list[threading.Thread] = []
    for runtime in runtimes:
        cfg = runtime.config
        parser = resolve_parser(cfg.parser_key)
        client = InstrumentClient(cfg.host, cfg.port, runtime.id_instrument)
        clients.append(client)
        threads.append(
            threading.Thread(
                target=client.recv_loop,
                args=(make_handler(runtime, parser),),
                name=f"instrument-{cfg.key}",
            )
        )

    def signal_handler(sig, frame):
        print("\n[*] Shutting down integration service...")
        for client in clients:
            client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"[*] Starting Integration Service for {len(threads)} instrument(s): "
          f"{', '.join(t.name for t in threads)}")
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
