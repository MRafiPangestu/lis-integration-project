"""Instrument status model — transport state versus connection state.

Pure and database-free. These tests are about the *semantics* of the two axes,
not about how any particular worker is wired, so they stay valid if the
listener or the client changes its internals.
"""
from __future__ import annotations

import pytest

from app.integration.instrument_status import (
    CONNECTION_CONNECTED,
    CONNECTION_DISCONNECTED,
    CONNECTION_STATES,
    CONNECTION_UNKNOWN,
    TRANSPORT_STATES,
    TRANSPORT_UNKNOWN,
    derive_connection_state,
    normalize_transport_state,
)


# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

def test_transport_vocabulary_is_exactly_what_the_workers_write():
    assert TRANSPORT_STATES == {"CONNECTED", "LISTENING", "RECONNECTING", "DISCONNECTED"}
    assert TRANSPORT_UNKNOWN not in TRANSPORT_STATES, "UNKNOWN is a fallback, never written"


def test_connection_vocabulary_has_exactly_three_values():
    assert CONNECTION_STATES == {"CONNECTED", "DISCONNECTED", "UNKNOWN"}


# --------------------------------------------------------------------------- #
# Transport normalisation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("state", sorted(TRANSPORT_STATES))
def test_known_transport_states_pass_through(state):
    assert normalize_transport_state(state) == state


@pytest.mark.parametrize("raw", [None, "", "   ", "connected", "Listening", "BANANA", "CONNECTED "])
def test_unknown_or_miscased_transport_states_become_unknown(raw):
    """Exact match only — a lowercase value is not silently accepted."""
    if raw == "CONNECTED ":
        assert normalize_transport_state(raw) == "CONNECTED", "surrounding whitespace is ignored"
    else:
        assert normalize_transport_state(raw) == TRANSPORT_UNKNOWN


# --------------------------------------------------------------------------- #
# The derivation: the whole point of the refactor
# --------------------------------------------------------------------------- #

def test_only_connected_transport_means_a_session_exists():
    assert derive_connection_state("CONNECTED") == CONNECTION_CONNECTED


@pytest.mark.parametrize("transport", ["LISTENING", "RECONNECTING", "DISCONNECTED"])
def test_every_other_known_transport_state_means_disconnected(transport):
    assert derive_connection_state(transport) == CONNECTION_DISCONNECTED


@pytest.mark.parametrize("raw", [None, "", "BANANA", "connected"])
def test_unknown_never_masquerades_as_connected(raw):
    assert derive_connection_state(raw) == CONNECTION_UNKNOWN


def test_listener_idle_and_client_retrying_agree_on_the_operator_answer():
    """The ambiguity this model exists to remove.

    A listener-mode instrument with no session (XN-550) and a client-mode
    instrument failing to dial (BC-5150) are the same physical reality: the
    instrument is not there. Their transport states differ; their connection
    state must not.
    """
    xn550_idle = derive_connection_state("LISTENING")
    bc5150_retrying = derive_connection_state("RECONNECTING")

    assert xn550_idle == bc5150_retrying == CONNECTION_DISCONNECTED
    assert normalize_transport_state("LISTENING") != normalize_transport_state("RECONNECTING"), (
        "the transport detail must survive the derivation, not be flattened away"
    )


def test_xn550_session_open_then_closed_tracks_the_connection_state():
    """Session opens -> CONNECTED; session closes while the listener stays up."""
    assert derive_connection_state("CONNECTED") == CONNECTION_CONNECTED
    # The listener returns to LISTENING after the session closes (contract §4.4).
    assert derive_connection_state("LISTENING") == CONNECTION_DISCONNECTED


def test_derivation_is_total_over_the_transport_vocabulary():
    """Every writable transport state maps to a defined connection state."""
    for state in TRANSPORT_STATES:
        assert derive_connection_state(state) in CONNECTION_STATES
