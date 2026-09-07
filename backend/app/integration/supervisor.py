"""Multi-instrument supervisor and runtime lifecycle for the integration service.

``InstrumentClient.recv_loop`` already recovers from every *connection* failure
(refused, timeout, DNS, clean close, read error, handler exception) by retrying
every few seconds while its thread stays alive. The one gap it cannot close is
its own thread terminating: today that is silent and unrecoverable and leaves a
stale ``CONNECTED``/``RECONNECTING`` row that the M7 status bar renders as
healthy.

This supervisor watches for exactly that condition — ``thread.is_alive()`` is
False and shutdown was not requested — and restarts the worker. It also makes
shutdown deterministic.

It deliberately never inspects sockets, ``connection_status`` or message timing:
those belong to the client's own retry loop, and a second reader would create
competing retries.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable

from app.integration.instruments import RuntimeInstrument, write_instrument_status

log = logging.getLogger(__name__)

# Tuning constants — not configuration fields. The fixed restart delay is what
# prevents a restart storm; a lab instrument may be offline for hours, so
# restarts are unlimited and not backed off.
POLL_INTERVAL_SECONDS = 2.0
RESTART_DELAY_SECONDS = 5.0
SHUTDOWN_JOIN_TIMEOUT_SECONDS = 10.0

# Given a RuntimeInstrument, build a fresh (client, unstarted thread) pair.
WorkerFactory = Callable[[RuntimeInstrument], "tuple[Any, Any]"]
StatusWriter = Callable[[int, str], None]


@dataclass
class Worker:
    """Runtime record for one managed instrument. Holds no ORM instances."""

    runtime: RuntimeInstrument
    client: Any
    thread: Any
    consecutive_restarts: int = 0
    # monotonic deadline after which a dead worker is rebuilt; None => not scheduled
    restart_due_at: "float | None" = None


class Supervisor:
    """Owns the worker set, the supervision tick, the run loop and shutdown."""

    def __init__(
        self,
        runtimes: list[RuntimeInstrument],
        worker_factory: WorkerFactory,
        *,
        shutdown_event: Event,
        status_writer: StatusWriter = write_instrument_status,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runtimes = list(runtimes)
        self._worker_factory = worker_factory
        self._shutdown_event = shutdown_event
        self._status_writer = status_writer
        self._clock = clock
        self._workers: list[Worker] = []

    @property
    def workers(self) -> list[Worker]:
        return self._workers

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        # Clear stale status rows from a previous run before any worker starts.
        for runtime in self._runtimes:
            self._status_writer(runtime.id_instrument, "RECONNECTING")

        for runtime in self._runtimes:
            client, thread = self._worker_factory(runtime)
            self._workers.append(Worker(runtime=runtime, client=client, thread=thread))
            thread.start()
            log.info("instrument '%s' worker started", runtime.config.key)

    def run(self) -> None:
        self.start()
        try:
            while not self._shutdown_event.is_set():
                self.tick()
                self._shutdown_event.wait(POLL_INTERVAL_SECONDS)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        for worker in self._workers:
            try:
                worker.client.stop()
            except Exception as exc:  # stop() must never block the shutdown sequence
                log.error(
                    "instrument '%s' client.stop() raised: %s",
                    worker.runtime.config.key, exc,
                )

        for worker in self._workers:
            worker.thread.join(SHUTDOWN_JOIN_TIMEOUT_SECONDS)
            if worker.thread.is_alive():
                # A non-daemon Python thread cannot be force-killed safely. The
                # supervisor stays bounded (it does not wait further) and still
                # records the authoritative final state below.
                log.error(
                    "instrument '%s' worker thread did not exit within %.0fs; "
                    "continuing shutdown without it",
                    worker.runtime.config.key, SHUTDOWN_JOIN_TIMEOUT_SECONDS,
                )

        # Authoritative final state for every managed instrument, including any
        # whose worker thread already died or is wedged.
        for runtime in self._runtimes:
            self._status_writer(runtime.id_instrument, "DISCONNECTED")

    # -- supervision -------------------------------------------------------

    def tick(self) -> None:
        """One supervision pass. Per-worker and independent: a dead worker is
        handled without touching any other worker's client or thread."""
        if self._shutdown_event.is_set():
            return
        for worker in self._workers:
            self._tick_worker(worker)

    def _tick_worker(self, worker: Worker) -> None:
        if worker.restart_due_at is not None:
            if self._clock() < worker.restart_due_at:
                return  # still inside the fixed restart delay
            client, thread = self._worker_factory(worker.runtime)
            worker.client = client
            worker.thread = thread
            worker.restart_due_at = None
            thread.start()
            log.warning(
                "instrument '%s' worker restarted (consecutive restarts=%d)",
                worker.runtime.config.key, worker.consecutive_restarts,
            )
            return

        if worker.thread.is_alive():
            # Alive covers both connected and the client's own reconnect wait —
            # never restart in that case.
            worker.consecutive_restarts = 0
            return

        # The one gap: the worker thread itself terminated.
        worker.consecutive_restarts += 1
        log.warning(
            "instrument '%s' worker thread terminated; scheduling restart in %.0fs "
            "(consecutive restarts=%d)",
            worker.runtime.config.key,
            RESTART_DELAY_SECONDS,
            worker.consecutive_restarts,
        )
        self._status_writer(worker.runtime.id_instrument, "RECONNECTING")
        worker.restart_due_at = self._clock() + RESTART_DELAY_SECONDS
