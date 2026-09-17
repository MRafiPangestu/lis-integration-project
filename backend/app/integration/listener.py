"""Listener (server) transport for instruments that dial the LIS — XN-550 Phase 1.

Implements docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md §4
(transport), §14 (multiple messages per session) and §16 (restart / reconnect)
for G1 ``raw_only``:

* bind the approved (host, port) — the approval scope itself is enforced by
  ``app.core.config`` (OD-XN-1); this module never widens it;
* accept only peers in the exact IP allowlist; anything else is closed with no
  read and no write;
* at most one active session per instrument; a new connection from an allowed
  peer supersedes the old one;
* idle sessions are never closed by the LIS, and no reconnect timer exists;
* after every successful read, exactly one ``0x06`` is written **before** the
  bytes are assembled or persisted (``ack_per_read_on_receive``, the only
  field-verified behaviour). ``0x06`` is the only byte this module can write;
  there is no NAK, no command and no ACK withholding as a protocol signal;
* every complete message / fragment is committed through the T1 store before
  the (Phase 1: no-op) hand-off.

It is independent of the HL7/MLLP ``InstrumentClient`` and never imports the
parser registry, the HL7 repository or the clinical models. Logs carry no
payload bytes.
"""
from __future__ import annotations

import datetime
import ipaddress
import logging
import socket
import threading
import time
from typing import Callable, Iterable, Optional, Protocol

from app.integration.astm.assembler import (
    AssemblerEvent,
    AstmRecordAssembler,
    CompleteMessage,
    Fragment,
)
from app.integration.raw_capture import (
    CLOSE_LIS_SHUTDOWN,
    CLOSE_PEER_CLOSED,
    CLOSE_PEER_RESET,
    CLOSE_PERSISTENCE_FAILURE,
    CLOSE_READ_ERROR,
    CLOSE_SUPERSEDED,
    TRANSPORT_MODE_LISTENER,
    RawCaptureStore,
    SessionContext,
    SessionCounters,
    sha256_hex,
)

log = logging.getLogger(__name__)

# The single byte this transport is ever allowed to write (contract §4.5).
ACK_BYTE = b"\x06"

ACK_POLICY_PER_READ_ON_RECEIVE = "ack_per_read_on_receive"

# Status values written to instruments.connection_status (contract §4.10).
STATUS_LISTENING = "LISTENING"
STATUS_CONNECTED = "CONNECTED"
STATUS_RECONNECTING = "RECONNECTING"

# Tuning constants — not configuration (module-level so tests can shorten them).
READ_SIZE = 4096
READ_TIMEOUT_SECONDS = 1.0  # only to observe stop/supersede requests; never closes a session
ACCEPT_TIMEOUT_SECONDS = 1.0
INCOMPLETE_MESSAGE_WARNING_SECONDS = 30.0
PERSIST_ATTEMPTS = 3
PERSIST_BACKOFF_SECONDS = (0.25, 0.75)
HEALTH_CHECK_INTERVAL_SECONDS = 5.0
HANDLER_JOIN_TIMEOUT_SECONDS = 5.0
LISTEN_BACKLOG = 4

StatusWriter = Callable[[int, str], None]
RawCommittedHook = Callable[[int], None]


class AckPolicy(Protocol):
    name: str

    def after_read(self, n_bytes: int) -> int:
        """Number of ACK bytes to write right after a read of *n_bytes* (0 or 1)."""

    def after_raw_commit(self) -> int:
        """Number of ACK bytes to write after a T1 commit (0 or 1)."""


class AckPerReadOnReceive:
    """Field-verified baseline: one ``0x06`` per successful read, before persistence."""

    name = ACK_POLICY_PER_READ_ON_RECEIVE

    def after_read(self, n_bytes: int) -> int:
        return 1 if n_bytes > 0 else 0

    def after_raw_commit(self) -> int:
        return 0


def resolve_ack_policy(name: str) -> AckPolicy:
    """Exact match only. ``ack_per_message_after_raw_commit`` is NOT FIELD-VERIFIED (OD-XN-4)."""
    if name == ACK_POLICY_PER_READ_ON_RECEIVE:
        return AckPerReadOnReceive()
    raise ValueError(f"unsupported listener ack_policy {name!r}")


def write_outbound(sock: socket.socket, payload: bytes) -> None:
    """The only write path of this module. Refuses anything that is not a single ACK byte."""
    if payload != ACK_BYTE:
        raise ValueError("listener transport may only write a single 0x06 ACK byte")
    sock.sendall(payload)


def raw_only_noop(id_message: int) -> None:
    """G1 ``raw_only`` hand-off after T1: deliberately does nothing (contract §19.4)."""
    return None


def _normalise_ip(value: str) -> str:
    return str(ipaddress.ip_address(value))


class SessionHandler:
    """Reads one accepted connection until it ends. Runs in its own thread."""

    def __init__(
        self,
        *,
        sock: socket.socket,
        ctx: SessionContext,
        id_session: int,
        instrument_key: str,
        store: RawCaptureStore,
        ack_policy: AckPolicy,
        clock: Callable[[], datetime.datetime],
        sleep: Callable[[float], None],
        on_raw_committed: RawCommittedHook,
    ) -> None:
        self._sock = sock
        self._ctx = ctx
        self.id_session = id_session
        self._key = instrument_key
        self._store = store
        self._ack = ack_policy
        self._clock = clock
        self._sleep = sleep
        self._on_raw_committed = on_raw_committed
        self._assembler = AstmRecordAssembler()
        self.counters = SessionCounters()
        self.close_reason: Optional[str] = None
        self.closed_at: Optional[datetime.datetime] = None
        self.close_recorded = False
        self._requested_reason: Optional[str] = None
        self._request_lock = threading.Lock()
        self._next_index = 0
        self._warned_tokens: set[str] = set()

    # -- control (called from other threads) ----------------------------------

    def request_close(self, reason: str) -> None:
        with self._request_lock:
            if self._requested_reason is None:
                self._requested_reason = reason
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _requested(self) -> Optional[str]:
        with self._request_lock:
            return self._requested_reason

    # -- main loop -------------------------------------------------------------

    def run(self) -> str:
        reason: Optional[str] = None
        last_byte_monotonic = time.monotonic()
        warned_incomplete = False
        try:
            while True:
                requested = self._requested()
                if requested is not None:
                    reason = requested
                    break
                try:
                    data = self._sock.recv(READ_SIZE)
                except socket.timeout:
                    if (
                        not warned_incomplete
                        and self._assembler.has_incomplete_message
                        and time.monotonic() - last_byte_monotonic >= INCOMPLETE_MESSAGE_WARNING_SECONDS
                    ):
                        warned_incomplete = True
                        log.warning(
                            "instrument %s session %s: message incomplete with no new bytes for %.0fs "
                            "(buffered up to offset %d); still waiting",
                            self._key, self.id_session, INCOMPLETE_MESSAGE_WARNING_SECONDS,
                            self._assembler.stream_offset,
                        )
                    continue
                except ConnectionResetError:
                    reason = self._requested() or CLOSE_PEER_RESET
                    break
                except OSError:
                    reason = self._requested() or CLOSE_READ_ERROR
                    break
                if not data:
                    reason = self._requested() or CLOSE_PEER_CLOSED
                    break

                read_at = self._clock()
                last_byte_monotonic = time.monotonic()
                warned_incomplete = False
                self.counters.bytes_received += len(data)
                self.counters.reads_count += 1

                # ACK first (contract §4.5), then assemble and persist.
                ack_failed = not self._send_acks(self._ack.after_read(len(data)))

                if not self._persist_all(self._assembler.feed(data, read_at)):
                    reason = CLOSE_PERSISTENCE_FAILURE
                    break
                if ack_failed:
                    reason = self._requested() or CLOSE_READ_ERROR
                    break
        finally:
            reason = self._finish(reason or CLOSE_READ_ERROR)
        return reason

    # -- helpers ---------------------------------------------------------------

    def _send_acks(self, count: int) -> bool:
        for _ in range(count):
            try:
                write_outbound(self._sock, ACK_BYTE)
            except OSError:
                return False
            self.counters.acks_sent += 1
        return True

    def _persist_all(self, events: Iterable[AssemblerEvent]) -> bool:
        events = list(events)
        for position, event in enumerate(events):
            if not self._persist(event):
                for lost in events[position + 1:]:
                    self._log_unpersisted(lost)
                return False
        return True

    def _persist(self, event: AssemblerEvent) -> bool:
        self._next_index += 1
        index = self._next_index
        last_exc: Optional[BaseException] = None
        for attempt in range(PERSIST_ATTEMPTS):
            try:
                id_message = self._store.persist_event(
                    self._ctx.id_instrument, self.id_session, index, event
                )
                break
            except Exception as exc:  # database / driver failure
                last_exc = exc
                if attempt < len(PERSIST_BACKOFF_SECONDS):
                    self._sleep(PERSIST_BACKOFF_SECONDS[attempt])
        else:
            log.error(
                "instrument %s session %s: T1 commit failed after %d attempts (%s); "
                "event NOT persisted",
                self._key, self.id_session, PERSIST_ATTEMPTS, type(last_exc).__name__,
            )
            self._log_unpersisted(event)
            return False

        if isinstance(event, Fragment):
            self.counters.fragments_count += 1
            self._warn_once(event.reason)
        else:
            self.counters.messages_completed += 1
            if event.byte_class_token is not None:
                self._warn_once(event.byte_class_token)
            else:
                self._send_acks(self._ack.after_raw_commit())
                self._on_raw_committed(id_message)
        return True

    def _warn_once(self, token: str) -> None:
        if token in self._warned_tokens:
            return
        self._warned_tokens.add(token)
        log.warning("instrument %s session %s: %s", self._key, self.id_session, token)

    def _log_unpersisted(self, event: AssemblerEvent) -> None:
        kind = "message" if isinstance(event, CompleteMessage) else "fragment"
        log.error(
            "instrument %s session %s: UNPERSISTED %s sha256=%s length=%d offsets=%d-%d "
            "(bytes already acknowledged; recover by manual retransmission)",
            self._key, self.id_session, kind, sha256_hex(event.raw), len(event.raw),
            event.offset_start, event.offset_end,
        )

    def _finish(self, reason: str) -> str:
        events = self._assembler.close()
        if reason == CLOSE_PERSISTENCE_FAILURE:
            for event in events:
                self._log_unpersisted(event)
        elif not self._persist_all(events):
            reason = CLOSE_PERSISTENCE_FAILURE
        try:
            self._sock.close()
        except OSError:
            pass
        self.closed_at = self._clock()
        self.close_reason = reason
        self.record_close()
        level = logging.INFO if reason in (CLOSE_PEER_RESET, CLOSE_PEER_CLOSED, CLOSE_SUPERSEDED, CLOSE_LIS_SHUTDOWN) else logging.WARNING
        log.log(
            level,
            "instrument %s session %s closed: %s (bytes=%d reads=%d acks=%d messages=%d fragments=%d)",
            self._key, self.id_session, reason, self.counters.bytes_received,
            self.counters.reads_count, self.counters.acks_sent,
            self.counters.messages_completed, self.counters.fragments_count,
        )
        return reason

    def record_close(self) -> bool:
        """Write the session close row. Retried by the listener after a store outage."""
        if self.close_recorded or self.close_reason is None:
            return self.close_recorded
        try:
            self._store.close_session(self.id_session, self.close_reason, self.counters, self.closed_at)
        except Exception as exc:
            log.error(
                "instrument %s session %s: could not record session close (%s): %s",
                self._key, self.id_session, self.close_reason, type(exc).__name__,
            )
            return False
        self.close_recorded = True
        return True


class ListenerTransport:
    """Supervisor-managed worker ``client`` for one listener-mode instrument."""

    def __init__(
        self,
        *,
        id_instrument: int,
        instrument_key: str,
        bind_host: str,
        bind_port: int,
        allowed_peers: Iterable[str],
        ack_policy: str,
        store: RawCaptureStore,
        status_writer: StatusWriter,
        clock: Callable[[], datetime.datetime] = datetime.datetime.now,
        sleep: Callable[[float], None] = time.sleep,
        on_raw_committed: RawCommittedHook = raw_only_noop,
    ) -> None:
        self._id_instrument = id_instrument
        self._key = instrument_key
        self._bind_host = _normalise_ip(bind_host)
        self._bind_port = bind_port
        self._allowed = frozenset(_normalise_ip(p) for p in allowed_peers)
        if not self._allowed:
            raise ValueError("listener requires a non-empty allowed_peers list")
        self._ack_policy = resolve_ack_policy(ack_policy)
        self._store = store
        self._status_writer = status_writer
        self._clock = clock
        self._sleep = sleep
        self._on_raw_committed = on_raw_committed

        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._listen_sock: Optional[socket.socket] = None
        self._handler: Optional[SessionHandler] = None
        self._handler_thread: Optional[threading.Thread] = None
        self._degraded = False
        self._unrecorded_closes: list[SessionHandler] = []
        self._last_status: Optional[str] = None
        self._bound = threading.Event()
        self.bound_port: Optional[int] = None

    # -- Supervisor contract ----------------------------------------------------

    def stop(self) -> None:
        """Idempotent; never blocks. The worker thread performs the orderly close."""
        self._stop.set()
        with self._lock:
            handler = self._handler
            listen_sock = self._listen_sock
        if handler is not None:
            handler.request_close(CLOSE_LIS_SHUTDOWN)
        if listen_sock is not None:
            try:
                listen_sock.close()
            except OSError:
                pass

    def wait_until_bound(self, timeout: float) -> bool:
        return self._bound.wait(timeout)

    def serve_forever(self) -> None:
        try:
            try:
                recovered = self._store.close_orphan_sessions(self._id_instrument, self._clock())
                if recovered:
                    log.warning(
                        "instrument %s: closed %d session row(s) left open by a previous run "
                        "(RECOVERED_AT_STARTUP)", self._key, recovered,
                    )
            except Exception as exc:
                log.error("instrument %s: orphan-session recovery failed (%s)", self._key, type(exc).__name__)
                self._enter_degraded()

            while not self._stop.is_set():
                # Reaping may enter degraded mode (and close the listening
                # socket), so it runs before the state checks below.
                self._reap_finished_handler()
                if self._degraded:
                    self._wait_for_store()
                    continue
                if self._listen_sock is None:
                    self._open_listen_socket()
                    continue
                listen_sock = self._listen_sock
                try:
                    conn, addr = listen_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                self._handle_accept(conn, addr)
        finally:
            self._shutdown()

    # -- internals ----------------------------------------------------------------

    def _open_listen_socket(self) -> None:
        family = socket.AF_INET6 if ipaddress.ip_address(self._bind_host).version == 6 else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: refuse port sharing
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self._bind_host, self._bind_port))
            sock.listen(LISTEN_BACKLOG)
            sock.settimeout(ACCEPT_TIMEOUT_SECONDS)
        except OSError:
            sock.close()
            raise  # worker thread ends; the Supervisor restarts it after its delay
        with self._lock:
            self._listen_sock = sock
        self.bound_port = sock.getsockname()[1]
        # Resume on the same port after a degraded-mode pause (matters only
        # when an ephemeral port 0 was requested, e.g. in tests).
        self._bind_port = self.bound_port
        log.info("instrument %s: listening on %s:%s", self._key, self._bind_host, self.bound_port)
        self._bound.set()
        if self._stop.is_set():  # stop() raced with bind
            self._close_listen_socket()
            return
        self._write_status(STATUS_LISTENING)

    def _close_listen_socket(self) -> None:
        with self._lock:
            sock, self._listen_sock = self._listen_sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _handle_accept(self, conn: socket.socket, addr) -> None:
        peer_ip, peer_port = addr[0], addr[1]
        try:
            allowed = _normalise_ip(peer_ip) in self._allowed
        except ValueError:
            allowed = False
        if not allowed:
            log.warning(
                "instrument %s: rejected connection from %s:%s (not in allowed_peers); "
                "no read, no write", self._key, peer_ip, peer_port,
            )
            try:
                conn.close()
            except OSError:
                pass
            return

        self._supersede_active_session(peer_ip, peer_port)
        if self._stop.is_set():
            conn.close()
            return

        local = conn.getsockname()
        ctx = SessionContext(
            id_instrument=self._id_instrument,
            transport_mode=TRANSPORT_MODE_LISTENER,
            local_address=str(local[0]),
            local_port=int(local[1]),
            peer_address=str(peer_ip),
            peer_port=int(peer_port),
            ack_policy=self._ack_policy.name,
            opened_at=self._clock(),
        )
        try:
            id_session = self._store.open_session(ctx)
        except Exception as exc:
            log.error(
                "instrument %s: could not open session row for %s:%s (%s); connection closed "
                "before any read", self._key, peer_ip, peer_port, type(exc).__name__,
            )
            try:
                conn.close()
            except OSError:
                pass
            self._enter_degraded()
            return

        conn.settimeout(READ_TIMEOUT_SECONDS)
        handler = SessionHandler(
            sock=conn,
            ctx=ctx,
            id_session=id_session,
            instrument_key=self._key,
            store=self._store,
            ack_policy=self._ack_policy,
            clock=self._clock,
            sleep=self._sleep,
            on_raw_committed=self._on_raw_committed,
        )
        thread = threading.Thread(
            target=handler.run, name=f"instrument-{self._key}-session-{id_session}"
        )
        with self._lock:
            self._handler = handler
            self._handler_thread = thread
        log.info(
            "instrument %s: session %s opened from %s:%s", self._key, id_session, peer_ip, peer_port
        )
        self._write_status(STATUS_CONNECTED)
        thread.start()

    def _supersede_active_session(self, peer_ip: str, peer_port: int) -> None:
        with self._lock:
            handler, thread = self._handler, self._handler_thread
        if handler is None or thread is None:
            return
        if thread.is_alive():
            log.info(
                "instrument %s: new connection from %s:%s supersedes session %s",
                self._key, peer_ip, peer_port, handler.id_session,
            )
            handler.request_close(CLOSE_SUPERSEDED)
            thread.join(HANDLER_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                log.error(
                    "instrument %s: superseded session %s did not finish within %.0fs",
                    self._key, handler.id_session, HANDLER_JOIN_TIMEOUT_SECONDS,
                )
        self._reap_finished_handler()

    def _reap_finished_handler(self) -> None:
        with self._lock:
            handler, thread = self._handler, self._handler_thread
            if handler is None or thread is None or thread.is_alive():
                return
            self._handler = None
            self._handler_thread = None
        if not handler.close_recorded:
            self._unrecorded_closes.append(handler)
        if handler.close_reason == CLOSE_PERSISTENCE_FAILURE:
            self._enter_degraded()
        elif not self._stop.is_set():
            self._write_status(STATUS_LISTENING)

    def _enter_degraded(self) -> None:
        """Contract §4.8: stop accepting connections until the store is healthy again."""
        if not self._degraded:
            log.error(
                "instrument %s: raw capture store unavailable; not accepting connections "
                "until a health check succeeds", self._key,
            )
        self._degraded = True
        self._close_listen_socket()
        self._write_status(STATUS_RECONNECTING)

    def _wait_for_store(self) -> None:
        if self._store.health_check():
            self._unrecorded_closes = [h for h in self._unrecorded_closes if not h.record_close()]
            log.info("instrument %s: raw capture store healthy again; resuming listener", self._key)
            self._degraded = False
            return
        self._stop.wait(HEALTH_CHECK_INTERVAL_SECONDS)

    def _write_status(self, status: str) -> None:
        if status == self._last_status:
            return
        self._last_status = status
        try:
            self._status_writer(self._id_instrument, status)
        except Exception as exc:  # status is best-effort; never breaks capture
            log.error("instrument %s: status write %s failed (%s)", self._key, status, type(exc).__name__)

    def _shutdown(self) -> None:
        self._stop.set()
        with self._lock:
            handler, thread = self._handler, self._handler_thread
        if handler is not None and thread is not None:
            handler.request_close(CLOSE_LIS_SHUTDOWN)
            thread.join(HANDLER_JOIN_TIMEOUT_SECONDS)
            if thread.is_alive():
                log.error(
                    "instrument %s: session %s did not finish within %.0fs during shutdown",
                    self._key, handler.id_session, HANDLER_JOIN_TIMEOUT_SECONDS,
                )
        self._close_listen_socket()
        log.info("instrument %s: listener stopped", self._key)


def build_listener_worker(
    runtime,
    *,
    store: RawCaptureStore,
    status_writer: StatusWriter,
) -> "tuple[ListenerTransport, threading.Thread]":
    """(client, unstarted thread) pair for the Supervisor, from a validated listener config."""
    config = runtime.config
    if config.mode != TRANSPORT_MODE_LISTENER:
        raise ValueError(f"instrument {config.key!r} is not a listener-mode instrument")
    transport = ListenerTransport(
        id_instrument=runtime.id_instrument,
        instrument_key=config.key,
        bind_host=config.host,
        bind_port=config.port,
        allowed_peers=config.allowed_peers or (),
        ack_policy=config.ack_policy,
        store=store,
        status_writer=status_writer,
    )
    thread = threading.Thread(target=transport.serve_forever, name=f"instrument-{config.key}")
    return transport, thread
