"""Instrument-agnostic message classification (M8.2).

Pure and database-free. Given a parsed message and a policy, decide whether the
message may enter clinical persistence.

The mechanism itself encodes no vendor-specific rule. The concrete production
policy for an instrument is a configuration decision
(``InstrumentConfig.classification_policy``); an instrument with no policy
configured resolves to ``strict`` -> ``UNCLASSIFIED``.

``bc5150_field_verified`` is the M8.2b policy: it is the only *evidence-based*
vendor rule, it is opt-in via configuration, and it is grounded solely in
committed field captures from the physical Mindray BC-5150. It stays fail-closed
— it identifies the "Background" run as NON_PATIENT and leaves everything else
UNCLASSIFIED (see ``_bc5150_field_verified``).

``bc5150_name_passthrough`` is an owner-approved **HIGH-RISK** BC-5150 policy
(see ``_bc5150_name_passthrough``). It is **not** evidence-validated: it keeps
the verified Background rule and then, as an explicit risk-accepted decision,
lets a *named* non-Background message become PATIENT_RESULT so observed patient
runs reach clinical persistence. It is opt-in per instrument and never a default;
``docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md`` §9.5 still records that a positive
*evidence* rule is NOT APPROVED — this policy is a separate operational choice,
parallel to ``unverified_passthrough``.
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
RULE_OBR3_BACKGROUND = "OBR3_BACKGROUND"
RULE_BC5150_BACKGROUND_ONLY = "BC5150_BACKGROUND_ONLY"
RULE_BC5150_NAME_PASSTHROUGH = "BC5150_NAME_PASSTHROUGH"
RULE_BC5150_NAME_ABSENT = "BC5150_NAME_ABSENT"

# ``parse_hl7_bc5150`` substitutes this literal for an absent / whitespace-only
# PID-5. "name populated" must therefore exclude it as well as "".
_BC5150_EMPTY_NAME_SENTINEL = "unknown"  # compared stripped + casefolded

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


def _bc5150_field_verified(parsed: "ParsedHL7") -> Classification:
    """Field-verified Mindray BC-5150 rule (M8.2b).

    Committed field captures prove exactly one thing: the instrument's own
    non-patient "Background" run is reported with OBR-3 literally "Background"
    and no patient identity. That is the only fact this policy encodes.

        OBR-3 (whitespace- and case-normalized) == "background"
            -> NON_PATIENT / OBR3_BACKGROUND
        anything else
            -> UNCLASSIFIED / BC5150_BACKGROUND_ONLY   (fail closed, like `strict`)

    It is deliberately NOT assumed that a non-"Background" message is a patient
    result: there is no field evidence for QC / calibration / maintenance /
    control categories, so those must not become PATIENT_RESULT merely by not
    matching "Background". Patient ingestion, when the owner accepts that risk,
    is a separate explicit decision (`unverified_passthrough`), not hidden here.

    Deliberately NOT used as discriminators (no field evidence supports them):
    PID-3 emptiness, low/zero numeric values, histogram/scattergram presence,
    Take/Blood/Test Mode, 99MRC identifiers, or the ORU^R01 trigger itself.
    """
    specimen = (parsed.order.specimen_no or "").strip().casefold()
    if specimen == "background":
        return Classification(MessageClass.NON_PATIENT, RULE_OBR3_BACKGROUND)
    return Classification(MessageClass.UNCLASSIFIED, RULE_BC5150_BACKGROUND_ONLY)


def _bc5150_name_passthrough(parsed: "ParsedHL7") -> Classification:
    """Owner-approved HIGH-RISK Mindray BC-5150 name passthrough — NOT evidence-validated.

    The only field-verified BC-5150 non-patient discriminator is OBR-3 ==
    "Background" (see ``_bc5150_field_verified``). This policy keeps that rule and
    then — as an explicit owner decision that accepts the risk — lets a *named*
    non-Background message through to clinical persistence:

        OBR-3 (stripped, casefolded) == "background"
            -> NON_PATIENT / OBR3_BACKGROUND               (field-verified)
        else, PID-5 name populated (not "" and not the "UNKNOWN" sentinel,
        compared stripped + casefolded)
            -> PATIENT_RESULT / BC5150_NAME_PASSTHROUGH     (HIGH RISK — unverified)
        else (empty / "UNKNOWN" name)
            -> UNCLASSIFIED / BC5150_NAME_ABSENT            (fail closed)

    This is a heuristic, not evidence. A mislabelled QC / calibration / control /
    maintenance run that happens to carry a name string in PID-5 would be
    persisted as a patient result — ``docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md``
    §9.5 still records that a positive *evidence* rule is NOT APPROVED. It is
    opt-in per instrument (``InstrumentConfig.classification_policy``) and never
    the default. A non-Background message is not promoted merely by not matching
    "Background": an unnamed one stays UNCLASSIFIED, exactly like
    ``bc5150_field_verified``. The parsed patient name is only read here, never
    rewritten — clinical persistence stores it verbatim.
    """
    specimen = (parsed.order.specimen_no or "").strip().casefold()
    if specimen == "background":
        return Classification(MessageClass.NON_PATIENT, RULE_OBR3_BACKGROUND)

    name = (parsed.patient.nama_lengkap or "").strip()
    if name and name.casefold() != _BC5150_EMPTY_NAME_SENTINEL:
        return Classification(
            MessageClass.PATIENT_RESULT, RULE_BC5150_NAME_PASSTHROUGH
        )

    return Classification(MessageClass.UNCLASSIFIED, RULE_BC5150_NAME_ABSENT)


_POLICIES: "dict[str, Policy]" = {
    "strict": _strict,
    "unverified_passthrough": _unverified_passthrough,
    "bc5150_field_verified": _bc5150_field_verified,
    "bc5150_name_passthrough": _bc5150_name_passthrough,
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
