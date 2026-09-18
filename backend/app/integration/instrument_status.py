"""Instrument status vocabulary — transport state versus connection state.

Two different questions were historically answered by one column, which is why
the same physical reality ("the instrument is not there") surfaced as
``LISTENING`` for a listener-mode instrument and ``RECONNECTING`` for a
client-mode one. This module keeps the two apart.

**Transport / runtime state** — what the LIS integration worker is doing. It is
persisted in ``instruments.connection_status`` and written by the listener
(§4.4 of the XN-550 contract), the client and the supervisor. Its vocabulary is
mode-specific on purpose: only a listener ever reports ``LISTENING``, and a
client reports ``DISCONNECTED`` from its own loop when it stops retrying.

**Instrument connection state** — whether there is an active communication
session with the physical instrument *right now*. This is the operator-facing
question. It is **derived, never stored**: exactly one transport state
(``CONNECTED``) means a session exists, and every other state means none does.

Deriving rather than storing is deliberate. A second persisted column could
drift out of step with the first and there would be no way to tell which one
was right; a derived value cannot disagree with its source.

**Liveness limitation.** Both values describe the *last persisted* state, not a
live probe. If the integration service is killed without a graceful shutdown,
the row keeps its last value — a dead session can read ``CONNECTED`` until the
instrument reconnects or the service restarts (XN-550 contract §4.7). There is
no heartbeat. ``last_status_at`` is the only staleness signal available, and it
records when the status last *changed*, not when the instrument was last seen.
"""
from __future__ import annotations

from typing import Optional

# --- transport / runtime state (persisted in instruments.connection_status) ---

TRANSPORT_CONNECTED = "CONNECTED"
TRANSPORT_LISTENING = "LISTENING"
TRANSPORT_RECONNECTING = "RECONNECTING"
TRANSPORT_DISCONNECTED = "DISCONNECTED"
TRANSPORT_UNKNOWN = "UNKNOWN"

#: Values an integration worker may write. ``UNKNOWN`` is not among them: it is
#: the API's fallback for a NULL or unrecognised column, never a written value.
TRANSPORT_STATES = frozenset(
    {TRANSPORT_CONNECTED, TRANSPORT_LISTENING, TRANSPORT_RECONNECTING, TRANSPORT_DISCONNECTED}
)

# --- instrument connection state (derived, operator-facing) ------------------

CONNECTION_CONNECTED = "CONNECTED"
CONNECTION_DISCONNECTED = "DISCONNECTED"
CONNECTION_UNKNOWN = "UNKNOWN"

CONNECTION_STATES = frozenset(
    {CONNECTION_CONNECTED, CONNECTION_DISCONNECTED, CONNECTION_UNKNOWN}
)

#: The only transport state that means a session with the instrument is open.
_TRANSPORT_MEANING_CONNECTED = frozenset({TRANSPORT_CONNECTED})


def normalize_transport_state(raw: Optional[str]) -> str:
    """Return a known transport state, or ``UNKNOWN``.

    ``None`` (never reported) and anything outside :data:`TRANSPORT_STATES`
    both become ``UNKNOWN``. Surrounding whitespace is ignored; the comparison
    is otherwise exact, so a lowercase or partial value is *not* silently
    accepted.
    """
    if raw is None:
        return TRANSPORT_UNKNOWN
    candidate = raw.strip()
    return candidate if candidate in TRANSPORT_STATES else TRANSPORT_UNKNOWN


def derive_connection_state(transport_state: Optional[str]) -> str:
    """Answer "is there an active session with the instrument?" from transport state.

    ``CONNECTED`` only when the worker reports an open session. ``UNKNOWN``
    only when the transport state itself is unknown — an unknown status must
    never read as connected. Everything else is ``DISCONNECTED``, which is what
    makes listener mode and client mode comparable: ``LISTENING`` with no
    session and ``RECONNECTING`` after a failed dial both mean the instrument
    is not there.
    """
    normalized = normalize_transport_state(transport_state)
    if normalized in _TRANSPORT_MEANING_CONNECTED:
        return CONNECTION_CONNECTED
    if normalized == TRANSPORT_UNKNOWN:
        return CONNECTION_UNKNOWN
    return CONNECTION_DISCONNECTED
