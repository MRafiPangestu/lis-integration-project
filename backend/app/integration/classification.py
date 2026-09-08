"""Instrument-agnostic message classification (M8.2).

Pure and database-free. Given a parsed message and a policy, decide whether the
message may enter clinical persistence.

The mechanism encodes no vendor-specific rule. The concrete production policy
for an instrument is a configuration decision
(``InstrumentConfig.classification_policy``); an instrument with no policy
configured resolves to ``strict`` -> ``UNCLASSIFIED``. The evidence-based
BC-5150 rule is M8.2b and is deliberately not implemented here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:  # avoid importing the parser package at module load
    from app.integration.parsers import ParsedHL7

log = logging.getLogger(__name__)


class MessageClass(str, Enum):
    PATIENT_RESULT = "PATIENT_RESULT"
    NON_PATIENT = "NON_PATIENT"
    UNCLASSIFIED = "UNCLASSIFIED"
    UNPARSEABLE = "UNPARSEABLE"


@dataclass(frozen=True)
class Classification:
    message_class: MessageClass
    classification_rule: str  # stable, machine-readable token


DEFAULT_POLICY = "strict"

# Stable rule tokens.
RULE_STRICT = "strict"
RULE_PASSTHROUGH = "unverified_passthrough"
RULE_UNPARSEABLE = "unparseable"
RULE_CLASSIFIER_ERROR = "classifier_error"

# A policy is a pure function over a successfully parsed message. It is never
# called with ``None`` — :func:`classify` handles the unparseable case.
Policy = Callable[["ParsedHL7"], Classification]


def _strict(parsed: "ParsedHL7") -> Classification:
    """No instrument auto-produces patient results without an explicit policy.
    Everything parseable stays ``UNCLASSIFIED`` until field evidence (M8.2b)
    defines a concrete rule."""
    return Classification(MessageClass.UNCLASSIFIED, RULE_STRICT)


def _unverified_passthrough(parsed: "ParsedHL7") -> Classification:
    """Treat every parsed message as a patient result. NOT evidence-based — only
    for an instrument whose owner has explicitly accepted this risk, or for
    tests that need the clinical path open."""
    return Classification(MessageClass.PATIENT_RESULT, RULE_PASSTHROUGH)


_POLICIES: "dict[str, Policy]" = {
    "strict": _strict,
    "unverified_passthrough": _unverified_passthrough,
}

KNOWN_POLICIES = frozenset(_POLICIES)


def resolve_policy(policy_name: Optional[str]) -> Policy:
    """Resolve a configured policy name to a policy function.

    ``None`` or an unknown name resolves to the strict default (fail closed).
    """
    if policy_name is None:
        return _POLICIES[DEFAULT_POLICY]
    policy = _POLICIES.get(policy_name)
    if policy is None:
        log.warning(
            "unknown classification_policy %r; falling back to %r",
            policy_name, DEFAULT_POLICY,
        )
        return _POLICIES[DEFAULT_POLICY]
    return policy


def classify(parsed: "Optional[ParsedHL7]", policy: Policy) -> Classification:
    """Classify one message.

    Pure, database-free and fail-closed: an unparseable message is
    ``UNPARSEABLE``, and a policy that raises yields ``UNCLASSIFIED`` rather
    than propagating.
    """
    if parsed is None:
        return Classification(MessageClass.UNPARSEABLE, RULE_UNPARSEABLE)
    try:
        return policy(parsed)
    except Exception:
        log.exception("classification policy raised; failing closed to UNCLASSIFIED")
        return Classification(MessageClass.UNCLASSIFIED, RULE_CLASSIFIER_ERROR)
