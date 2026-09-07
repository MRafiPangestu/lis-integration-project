"""M8.1-B supervisor tests.

No sockets and no live PostgreSQL: fake clients, fake threads, a fake clock and
an injected status writer.
"""
import logging
import threading

import pytest

from app.core.config import InstrumentConfig
from app.integration.instruments import RuntimeInstrument
from app.integration.supervisor import (
    RESTART_DELAY_SECONDS,
    SHUTDOWN_JOIN_TIMEOUT_SECONDS,
    Supervisor,
)
from run_integration import make_signal_handler


# --- fakes -----------------------------------------------------------------

class FakeThread:
    def __init__(self, *, alive_after_start: bool = True, wedged: bool = False):
        self._alive = False
        self._alive_after_start = alive_after_start
        self._wedged = wedged
        self.start_count = 0
        self.join_timeouts: list = []

    def start(self):
        self.start_count += 1
        self._alive = self._alive_after_start

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        self.join_timeouts.append(timeout)
        if not self._wedged:
            self._alive = False

    def die(self):
        self._alive = False


class FakeClient:
    def __init__(self):
        self.stop_count = 0

    def stop(self):
        self.stop_count += 1


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class StatusRecorder:
    def __init__(self):
        self.writes: list[tuple[int, str]] = []

    def __call__(self, id_instrument: int, status: str):
        self.writes.append((id_instrument, status))

    def statuses_for(self, id_instrument: int) -> list[str]:
        return [s for i, s in self.writes if i == id_instrument]


def make_runtime(key: str, id_instrument: int) -> RuntimeInstrument:
    cfg = InstrumentConfig(
        key=key,
        instrument_name=f"Machine {key}",
        host="127.0.0.1",
        port=5100,
        mode="client",
        parser_key="bc5150_hl7",
        identity_prefix="BC5150-",
        enabled=True,
    )
    return RuntimeInstrument(config=cfg, id_instrument=id_instrument)


class RecordingFactory:
    """Worker factory over fakes. ``born_dead`` simulates a thread that
    terminates immediately (used for crash-loop tests)."""

    def __init__(self, *, born_dead: bool = False, wedged: bool = False):
        self.born_dead = born_dead
        self.wedged = wedged
        self.calls: list[RuntimeInstrument] = []
        self.clients: list[FakeClient] = []
        self.threads: list[FakeThread] = []

    def __call__(self, runtime: RuntimeInstrument):
        self.calls.append(runtime)
        client = FakeClient()
        thread = FakeThread(
            alive_after_start=not self.born_dead, wedged=self.wedged
        )
        self.clients.append(client)
        self.threads.append(thread)
        return client, thread


def build(runtimes, factory, clock=None):
    ev = threading.Event()
    status = StatusRecorder()
    sup = Supervisor(
        runtimes,
        factory,
        shutdown_event=ev,
        status_writer=status,
        clock=clock or FakeClock(),
    )
    return sup, ev, status


# --- startup -------------------------------------------------------------

def test_startup_reset_writes_reconnecting_before_workers_start():
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    sup, ev, status = build([rt], factory)

    sup.start()

    assert status.writes[0] == (1, "RECONNECTING")
    assert factory.threads[0].start_count == 1


# --- healthy workers ----------------------------------------------------

def test_alive_workers_trigger_no_action():
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    sup, ev, status = build([rt], factory)
    sup.start()
    status.writes.clear()

    sup.tick()

    assert status.writes == []
    assert len(factory.calls) == 1  # no rebuild
    assert factory.threads[0].start_count == 1


def test_alive_but_reconnecting_worker_is_never_restarted():
    # An alive thread whose client is mid-reconnect looks identical to a healthy
    # one to the supervisor: is_alive() is True, so it is left alone.
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    sup, ev, status = build([rt], factory)
    sup.start()
    status.writes.clear()

    for _ in range(5):
        sup.tick()

    assert len(factory.calls) == 1
    assert status.writes == []


# --- dead worker detection & restart ----------------------------------

def test_dead_worker_writes_reconnecting():
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    clock = FakeClock()
    sup, ev, status = build([rt], factory, clock=clock)
    sup.start()
    status.writes.clear()

    factory.threads[0].die()
    sup.tick()

    assert status.writes == [(1, "RECONNECTING")]
    assert sup.workers[0].consecutive_restarts == 1


def test_dead_worker_within_delay_is_not_restarted_yet():
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    clock = FakeClock()
    sup, ev, status = build([rt], factory, clock=clock)
    sup.start()

    factory.threads[0].die()
    sup.tick()  # schedules restart at now + RESTART_DELAY_SECONDS
    clock.advance(RESTART_DELAY_SECONDS - 0.01)
    sup.tick()

    assert len(factory.calls) == 1  # still not rebuilt


def test_dead_worker_past_delay_gets_new_client_and_thread():
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    clock = FakeClock()
    sup, ev, status = build([rt], factory, clock=clock)
    sup.start()

    old_client = sup.workers[0].client
    old_thread = sup.workers[0].thread
    old_thread.die()

    sup.tick()
    clock.advance(RESTART_DELAY_SECONDS)
    sup.tick()

    assert len(factory.calls) == 2
    assert sup.workers[0].client is not old_client
    assert sup.workers[0].thread is not old_thread
    assert sup.workers[0].thread.start_count == 1
    assert sup.workers[0].restart_due_at is None


# --- isolation between workers ---------------------------------------

def test_one_dead_one_alive_restarts_only_the_dead_one():
    rt_a = make_runtime("a", 1)
    rt_b = make_runtime("b", 2)
    factory = RecordingFactory()
    clock = FakeClock()
    sup, ev, status = build([rt_a, rt_b], factory, clock=clock)
    sup.start()
    status.writes.clear()

    alive_client_b = sup.workers[1].client
    alive_thread_b = sup.workers[1].thread
    sup.workers[0].thread.die()

    sup.tick()
    clock.advance(RESTART_DELAY_SECONDS)
    sup.tick()

    # worker a rebuilt
    assert len(factory.calls) == 3  # 2 initial + 1 restart
    # worker b untouched
    assert sup.workers[1].client is alive_client_b
    assert sup.workers[1].thread is alive_thread_b
    assert sup.workers[1].consecutive_restarts == 0
    assert status.statuses_for(2) == []


def test_crash_loop_restarts_repeatedly_without_affecting_the_other_worker():
    rt_a = make_runtime("a", 1)
    rt_b = make_runtime("b", 2)
    # born_dead: every (re)built worker terminates immediately -> a crash loop.
    factory = RecordingFactory(born_dead=True)
    clock = FakeClock()
    sup, ev, status = build([rt_a, rt_b], factory, clock=clock)

    sup.start()
    sup.workers[1].thread._alive = True  # worker b is healthy and stays so
    status.writes.clear()  # drop the startup RECONNECTING reset

    n = 4
    for _ in range(n):
        sup.tick()                       # detect death, schedule
        clock.advance(RESTART_DELAY_SECONDS)
        sup.tick()                       # rebuild

    assert sup.workers[0].consecutive_restarts == n
    # 2 initial builds + n rebuilds of worker a
    assert len(factory.calls) == 2 + n
    # worker b never rebuilt, never flagged
    assert sup.workers[1].consecutive_restarts == 0
    assert status.statuses_for(2) == []


# --- shutdown ---------------------------------------------------------

def test_shutdown_stops_joins_and_writes_disconnected_for_all():
    rt_a = make_runtime("a", 1)
    rt_b = make_runtime("b", 2)
    factory = RecordingFactory()
    sup, ev, status = build([rt_a, rt_b], factory)
    sup.start()
    status.writes.clear()

    sup.shutdown()

    for client in factory.clients:
        assert client.stop_count == 1
    for thread in factory.threads:
        assert thread.join_timeouts == [SHUTDOWN_JOIN_TIMEOUT_SECONDS]
    assert status.statuses_for(1) == ["DISCONNECTED"]
    assert status.statuses_for(2) == ["DISCONNECTED"]


def test_shutdown_writes_disconnected_even_when_a_worker_already_died():
    rt_a = make_runtime("a", 1)
    rt_b = make_runtime("b", 2)
    factory = RecordingFactory()
    sup, ev, status = build([rt_a, rt_b], factory)
    sup.start()
    status.writes.clear()

    sup.workers[0].thread.die()  # worker a's thread already gone
    sup.shutdown()

    assert status.statuses_for(1) == ["DISCONNECTED"]
    assert status.statuses_for(2) == ["DISCONNECTED"]


def test_shutdown_suppresses_restart():
    rt = make_runtime("a", 1)
    factory = RecordingFactory()
    clock = FakeClock()
    sup, ev, status = build([rt], factory, clock=clock)
    sup.start()

    sup.workers[0].thread.die()
    ev.set()

    sup.tick()
    clock.advance(RESTART_DELAY_SECONDS * 10)
    sup.tick()

    assert len(factory.calls) == 1  # no rebuild while shutting down


def test_join_timeout_is_logged_and_status_write_still_happens(caplog):
    rt = make_runtime("a", 1)
    factory = RecordingFactory(wedged=True)  # join() never clears is_alive()
    sup, ev, status = build([rt], factory)
    sup.start()
    status.writes.clear()

    with caplog.at_level(logging.ERROR, logger="app.integration.supervisor"):
        sup.shutdown()

    assert any("did not exit within" in r.message for r in caplog.records)
    assert status.statuses_for(1) == ["DISCONNECTED"]


# --- signal handler -------------------------------------------------

def test_signal_handler_sets_flag_without_raising_system_exit():
    ev = threading.Event()
    handler = make_signal_handler(ev)

    handler(2, None)  # SIGINT

    assert ev.is_set()
