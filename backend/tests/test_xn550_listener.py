"""XN-550 Phase 1 — listener transport (contract §4, §14, §16).

Real loopback TCP sockets, an in-memory fake store and a status recorder. No
database, no instrument. Synthetic payloads only (obviously synthetic labels).
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import pathlib
import socket
import struct
import threading
import time

import pytest

from app.core.config import InstrumentConfig
from app.integration import listener as listener_module
from app.integration.astm.assembler import (
    FRAGMENT_INCOMPLETE_AT_CLOSE,
    TOKEN_E1381_OR_CONTROL_BYTE,
    CompleteMessage,
    Fragment,
)
from app.integration.instruments import RuntimeInstrument
from app.integration.listener import (
    ACK_BYTE,
    AckPerReadOnReceive,
    ListenerTransport,
    build_listener_worker,
    raw_only_noop,
    resolve_ack_policy,
    write_outbound,
)
from app.integration.raw_capture import (
    CLOSE_LIS_SHUTDOWN,
    CLOSE_PEER_CLOSED,
    CLOSE_PEER_RESET,
    CLOSE_PERSISTENCE_FAILURE,
    CLOSE_SUPERSEDED,
)

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)
SENTINEL_LABEL = "SYNTH-LOGCHECK-7F3A"
WAIT = 5.0


def synthetic_message(label: str = SENTINEL_LABEL, results: int = 3) -> bytes:
    records = [
        "H|\\^&|||SYNTH-ANALYZER^0^0^^^^SYNTH0001||||||||E1394-97",
        "P|1",
        "C|1||",
        f"O|1||^^{label}^M|^^^^SYNTH1",
        "C|1||",
    ]
    records += [f"R|{i}|^^^^SYN{i}^1|{i}.0|u||N||F||lab||20260917100000" for i in range(1, results + 1)]
    records += ["C|1||", "L|1|N"]
    return ("\r".join(records) + "\r").encode("ascii")


def wait_for(predicate, timeout: float = WAIT, interval: float = 0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("condition not met within timeout")


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class FakeStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sessions: dict[int, dict] = {}
        self.events: list[dict] = []
        self.orphan_calls: list[int] = []
        self.fail_persist = False
        self.healthy = True
        self._next_session = 0
        self._next_message = 0

    def open_session(self, ctx):
        with self.lock:
            self._next_session += 1
            self.sessions[self._next_session] = {"ctx": ctx, "reason": None, "counters": None}
            return self._next_session

    def close_session(self, id_session, reason, counters, closed_at):
        with self.lock:
            self.sessions[id_session].update(
                reason=reason, counters=dataclasses.replace(counters), closed_at=closed_at
            )

    def close_orphan_sessions(self, id_instrument, closed_at):
        with self.lock:
            self.orphan_calls.append(id_instrument)
        return 0

    def persist_event(self, id_instrument, id_session, session_message_index, event):
        with self.lock:
            if self.fail_persist:
                raise RuntimeError("simulated database outage")
            self._next_message += 1
            self.events.append(
                dict(
                    id_message=self._next_message,
                    id_instrument=id_instrument,
                    id_session=id_session,
                    index=session_message_index,
                    event=event,
                )
            )
            return self._next_message

    def health_check(self):
        return self.healthy

    # helpers
    def closed(self, id_session):
        with self.lock:
            s = self.sessions.get(id_session)
            return s is not None and s["reason"] is not None

    def events_for(self, id_session):
        with self.lock:
            return [e for e in self.events if e["id_session"] == id_session]


class StatusRecorder:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.writes: list[str] = []

    def __call__(self, id_instrument, status):
        with self.lock:
            self.writes.append(status)

    def last(self):
        with self.lock:
            return self.writes[-1] if self.writes else None


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    monkeypatch.setattr(listener_module, "READ_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(listener_module, "ACCEPT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(listener_module, "HEALTH_CHECK_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(listener_module, "PERSIST_BACKOFF_SECONDS", (0.0, 0.0))


@pytest.fixture
def start_listener():
    started: list[tuple[ListenerTransport, threading.Thread]] = []

    def _start(*, allowed=("127.0.0.1",), store=None, status=None, on_raw_committed=raw_only_noop):
        store = store or FakeStore()
        status = status or StatusRecorder()
        transport = ListenerTransport(
            id_instrument=3,
            instrument_key="sysmex_xn550_test",
            bind_host="127.0.0.1",
            bind_port=0,
            allowed_peers=allowed,
            ack_policy="ack_per_read_on_receive",
            store=store,
            status_writer=status,
            on_raw_committed=on_raw_committed,
        )
        thread = threading.Thread(target=transport.serve_forever, daemon=True)
        thread.start()
        assert transport.wait_until_bound(WAIT)
        started.append((transport, thread))
        return transport, thread, store, status

    yield _start

    for transport, thread in started:
        transport.stop()
        thread.join(10)
        assert not thread.is_alive(), "listener thread did not stop"


def connect(port: int) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=WAIT)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def drain(sock: socket.socket, quiet: float = 0.3) -> bytes:
    """Read until the peer has been silent for *quiet* seconds (or closed)."""
    received = bytearray()
    sock.settimeout(quiet)
    while True:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        except OSError:
            break
        if not chunk:
            break
        received += chunk
    return bytes(received)


# --------------------------------------------------------------------------- #
# Acceptance / peer policy
# --------------------------------------------------------------------------- #


def test_configured_peer_is_accepted_and_session_provenance_recorded(start_listener):
    transport, _, store, status = start_listener()
    client = connect(transport.bound_port)
    try:
        wait_for(lambda: store.sessions)
        ctx = store.sessions[1]["ctx"]
        assert ctx.id_instrument == 3
        assert ctx.transport_mode == "listener"
        assert ctx.ack_policy == "ack_per_read_on_receive"
        assert (ctx.peer_address, ctx.peer_port) == ("127.0.0.1", client.getsockname()[1])
        assert (ctx.local_address, ctx.local_port) == ("127.0.0.1", transport.bound_port)
        wait_for(lambda: status.last() == "CONNECTED")
        assert status.writes[:2] == ["LISTENING", "CONNECTED"]
        assert store.orphan_calls == [3]
    finally:
        client.close()
    wait_for(lambda: store.closed(1))
    assert store.sessions[1]["reason"] == CLOSE_PEER_CLOSED
    wait_for(lambda: status.last() == "LISTENING")


def test_unauthorised_peer_is_closed_without_read_or_ack(start_listener):
    transport, _, store, _ = start_listener(allowed=("10.0.0.11",))
    client = connect(transport.bound_port)
    try:
        try:
            client.sendall(FIXTURE.read_bytes())
        except OSError:
            pass
        received = drain(client, quiet=0.5)
    finally:
        client.close()
    assert ACK_BYTE not in received and received == b""
    time.sleep(0.2)
    assert store.sessions == {} and store.events == []


# --------------------------------------------------------------------------- #
# Framing over TCP, ACK discipline, raw preservation
# --------------------------------------------------------------------------- #


def test_message_split_across_reads_is_persisted_once_with_one_ack_per_read(start_listener, caplog):
    caplog.set_level("DEBUG")
    fixture = FIXTURE.read_bytes()
    transport, _, store, _ = start_listener()
    client = connect(transport.bound_port)
    cuts = [300, 1100, 1900, 2500]
    parts = [fixture[a:b] for a, b in zip([0, *cuts], [*cuts, len(fixture)])]
    for part in parts:
        client.sendall(part)
        time.sleep(0.15)
    wait_for(lambda: store.events_for(1))
    acks = drain(client)
    client.close()
    wait_for(lambda: store.closed(1))

    counters = store.sessions[1]["counters"]
    events = store.events_for(1)
    assert len(events) == 1
    event = events[0]["event"]
    assert isinstance(event, CompleteMessage)
    assert event.raw == fixture
    assert hashlib.sha256(event.raw).hexdigest() == hashlib.sha256(fixture).hexdigest()
    assert event.read_count == counters.reads_count >= 2
    assert counters.bytes_received == len(fixture)
    assert counters.acks_sent == counters.reads_count
    assert acks == ACK_BYTE * counters.reads_count  # exactly 0x06, once per read, nothing else
    assert counters.messages_completed == 1 and counters.fragments_count == 0


def test_multiple_messages_in_one_send_are_persisted_in_order(start_listener):
    transport, _, store, _ = start_listener()
    messages = [synthetic_message("SYNTH-M1"), FIXTURE.read_bytes(), synthetic_message("SYNTH-M3", 9)]
    client = connect(transport.bound_port)
    client.sendall(b"".join(messages))
    wait_for(lambda: len(store.events_for(1)) == 3)
    received = drain(client)
    client.close()
    wait_for(lambda: store.closed(1))

    events = store.events_for(1)
    assert [e["index"] for e in events] == [1, 2, 3]
    assert [e["event"].raw for e in events] == messages
    offsets = [(e["event"].offset_start, e["event"].offset_end) for e in events]
    assert offsets[0][0] == 0
    assert all(prev[1] == nxt[0] for prev, nxt in zip(offsets, offsets[1:]))
    assert set(received) <= {0x06} and 0x15 not in received


def test_close_mid_message_persists_incomplete_fragment(start_listener):
    transport, _, store, _ = start_listener()
    partial = synthetic_message("SYNTH-PARTIAL")[:60]
    client = connect(transport.bound_port)
    client.sendall(partial)
    drain(client)  # ensures the server has read (and ACKed) the bytes
    client.close()
    wait_for(lambda: store.closed(1))
    assert store.sessions[1]["reason"] == CLOSE_PEER_CLOSED
    events = store.events_for(1)
    assert len(events) == 1
    assert isinstance(events[0]["event"], Fragment)
    assert events[0]["event"].reason == FRAGMENT_INCOMPLETE_AT_CLOSE
    assert events[0]["event"].raw == partial


def test_peer_reset_is_recorded(start_listener):
    transport, _, store, _ = start_listener()
    client = connect(transport.bound_port)
    client.sendall(b"H|\\^&")
    drain(client)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    client.close()  # abortive close -> RST
    wait_for(lambda: store.closed(1))
    assert store.sessions[1]["reason"] == CLOSE_PEER_RESET
    assert store.events_for(1)[0]["event"].raw == b"H|\\^&"


def test_new_connection_supersedes_active_session(start_listener):
    transport, _, store, status = start_listener()
    first = connect(transport.bound_port)
    first.sendall(b"H|\\^&|||SYNTH-OLD\r")
    drain(first)
    second = connect(transport.bound_port)
    try:
        wait_for(lambda: store.closed(1))
        assert store.sessions[1]["reason"] == CLOSE_SUPERSEDED
        assert [e["event"].raw for e in store.events_for(1)] == [b"H|\\^&|||SYNTH-OLD\r"]
        assert drain(first) == b""  # old socket was closed by the LIS

        wait_for(lambda: 2 in store.sessions)
        message = synthetic_message("SYNTH-NEW")
        second.sendall(message)
        wait_for(lambda: store.events_for(2))
        assert store.events_for(2)[0]["event"].raw == message
        assert not store.closed(2)
        assert status.last() == "CONNECTED"
    finally:
        first.close()
        second.close()


def test_idle_session_remains_open(start_listener):
    transport, _, store, _ = start_listener()
    client = connect(transport.bound_port)
    try:
        wait_for(lambda: store.sessions)
        time.sleep(1.0)  # 20 read timeouts at the patched 50 ms
        assert not store.closed(1)
        client.sendall(synthetic_message("SYNTH-AFTER-IDLE"))
        wait_for(lambda: store.events_for(1))
        assert drain(client) == ACK_BYTE
        assert not store.closed(1)
    finally:
        client.close()


# --------------------------------------------------------------------------- #
# Hand-off, byte classes, shutdown, persistence failure
# --------------------------------------------------------------------------- #


def test_raw_only_handoff_runs_only_for_pending_complete_messages(start_listener):
    committed: list[int] = []
    transport, _, store, _ = start_listener(on_raw_committed=committed.append)
    good = synthetic_message("SYNTH-GOOD")
    control = synthetic_message("SYNTH-STX").replace(b"P|1\r", b"P|1\x02\r")
    client = connect(transport.bound_port)
    client.sendall(good + control)
    wait_for(lambda: len(store.events_for(1)) == 2)
    client.close()
    events = store.events_for(1)
    assert events[1]["event"].byte_class_token == TOKEN_E1381_OR_CONTROL_BYTE
    assert committed == [events[0]["id_message"]]
    assert raw_only_noop(123) is None


def test_stop_closes_active_session_as_lis_shutdown_and_releases_the_port(start_listener):
    transport, thread, store, _ = start_listener()
    client = connect(transport.bound_port)
    client.sendall(b"H|\\^&|||SYNTH-SHUTDOWN\r")
    drain(client)
    port = transport.bound_port
    transport.stop()
    thread.join(10)
    assert not thread.is_alive()
    assert store.sessions[1]["reason"] == CLOSE_LIS_SHUTDOWN
    assert store.events_for(1)[0]["event"].reason == FRAGMENT_INCOMPLETE_AT_CLOSE
    client.close()
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=1).close()


def test_persistence_failure_closes_session_and_pauses_accepting_until_healthy(start_listener, caplog):
    caplog.set_level("DEBUG")
    store = FakeStore()
    store.fail_persist = True
    store.healthy = False
    transport, _, _, status = start_listener(store=store)
    port = transport.bound_port

    client = connect(port)
    client.sendall(synthetic_message())
    wait_for(lambda: store.closed(1))
    client.close()
    assert store.sessions[1]["reason"] == CLOSE_PERSISTENCE_FAILURE
    wait_for(lambda: status.last() == "RECONNECTING")

    def refused():
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        except OSError:
            return True
        return False

    wait_for(refused)

    store.fail_persist = False
    store.healthy = True
    wait_for(lambda: status.last() == "LISTENING")
    client = connect(port)
    client.sendall(synthetic_message("SYNTH-RECOVERED"))
    wait_for(lambda: store.events)
    client.close()
    assert store.events[0]["id_session"] == 2

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "UNPERSISTED message sha256=" in text
    assert SENTINEL_LABEL not in text and "SYNTH-RECOVERED" not in text and "PNG&R&" not in text


# --------------------------------------------------------------------------- #
# Static guarantees
# --------------------------------------------------------------------------- #


def test_only_a_single_ack_byte_can_ever_be_written():
    class RecordingSocket:
        def __init__(self):
            self.sent = []

        def sendall(self, data):
            self.sent.append(data)

    sock = RecordingSocket()
    write_outbound(sock, b"\x06")
    for forbidden in (b"\x15", b"\x06\x06", b"", b"\x05", b"\x04"):
        with pytest.raises(ValueError):
            write_outbound(sock, forbidden)
    assert sock.sent == [b"\x06"]
    assert ACK_BYTE == b"\x06"


def test_listener_module_has_no_nak_path_and_no_other_send_calls():
    source = pathlib.Path(listener_module.__file__).read_text(encoding="utf-8")
    assert "\\x15" not in source and "0x15" not in source
    assert source.count(".sendall(") == 1 and ".send(" not in source


def test_ack_policy_is_exact_and_unverified_policy_is_unavailable():
    assert isinstance(resolve_ack_policy("ack_per_read_on_receive"), AckPerReadOnReceive)
    for name in ("ack_per_message_after_raw_commit", "ACK_PER_READ_ON_RECEIVE", "nak", ""):
        with pytest.raises(ValueError):
            resolve_ack_policy(name)
    policy = AckPerReadOnReceive()
    assert (policy.after_read(1), policy.after_read(0), policy.after_raw_commit()) == (1, 0, 0)


def test_listener_requires_a_non_empty_allowlist():
    with pytest.raises(ValueError):
        ListenerTransport(
            id_instrument=3, instrument_key="x", bind_host="127.0.0.1", bind_port=0,
            allowed_peers=(), ack_policy="ack_per_read_on_receive",
            store=FakeStore(), status_writer=StatusRecorder(),
        )


def test_listener_module_does_not_import_parsers_hl7_path_or_clinical_models():
    tree = ast.parse(pathlib.Path(listener_module.__file__).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    forbidden = {
        "app.integration.parsers", "app.integration.parsers.registry", "app.integration.parsers.hl7",
        "app.integration.repository", "app.integration.client", "app.integration.mllp",
        "app.integration.classification", "app.models",
    }
    assert not (modules & forbidden), modules & forbidden


def test_bind_conflict_raises_so_the_supervisor_can_restart():
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    try:
        transport = ListenerTransport(
            id_instrument=3, instrument_key="x", bind_host="127.0.0.1",
            bind_port=blocker.getsockname()[1], allowed_peers=("127.0.0.1",),
            ack_policy="ack_per_read_on_receive", store=FakeStore(), status_writer=StatusRecorder(),
        )
        with pytest.raises(OSError):
            transport.serve_forever()
    finally:
        blocker.close()


def test_build_listener_worker_uses_the_validated_config():
    config = InstrumentConfig(
        key="sysmex_xn550",
        instrument_name="Sysmex XN-550",
        host="10.0.0.10",
        port=5001,
        mode="listener",
        allowed_peers=["10.0.0.11"],
        ack_policy="ack_per_read_on_receive",
        ingestion_stage="raw_only",
    )
    transport, thread = build_listener_worker(
        RuntimeInstrument(config=config, id_instrument=3), store=FakeStore(), status_writer=StatusRecorder()
    )
    assert isinstance(transport, ListenerTransport)
    assert not thread.is_alive()
    assert thread.name == "instrument-sysmex_xn550"
