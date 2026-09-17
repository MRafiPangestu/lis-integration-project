"""XN-550 external corpus conformance — LOCAL, OPT-IN (contract §20.2 layer 13, AC-XN-28).

Skipped unless the environment variable ``XN550_EVIDENCE_ROOT`` points at the
frozen field-evidence directory, which lives outside the repository and contains
PHI. The test reads raw files read-only, asserts **aggregates only**, and never
prints, logs or stores field values. Nothing from the evidence is committed.
"""
from __future__ import annotations

import os
import pathlib
from collections import Counter

import pytest

from app.integration.parsers.xn550_astm import (
    ConformantMessage,
    EnvelopeDeviation,
    classify_xn550,
    parse_xn550_astm,
)
from app.integration.classification import MessageClass

EVIDENCE_ROOT = os.environ.get("XN550_EVIDENCE_ROOT")

pytestmark = pytest.mark.skipif(
    not EVIDENCE_ROOT, reason="opt-in: set XN550_EVIDENCE_ROOT to the external XN-550 evidence root"
)


def test_external_corpus_conforms_in_aggregate():
    files = sorted(pathlib.Path(EVIDENCE_ROOT).rglob("*.astm"))
    assert len(files) == 22, "unexpected evidence file count"

    outcomes: Counter = Counter()
    kinds: Counter = Counter()
    novelty_count = 0
    for path in files:
        result = parse_xn550_astm(path.read_bytes())
        classification = classify_xn550(result)
        assert classification.message_class != MessageClass.PATIENT_RESULT
        outcomes[classification.classification_rule] += 1
        if isinstance(result, ConformantMessage):
            kinds.update(r.item_kind for r in result.results)
            novelty_count += len(result.novelties)
        else:
            assert isinstance(result, EnvelopeDeviation)

    assert outcomes == Counter({"XN550_ENVELOPE_CONFORMANT": 21, "XN550_DEV_RECORD_SEQUENCE": 1})
    assert kinds == Counter({"MEASURED": 516, "INTERPRETIVE": 186, "FLAG_ONLY": 37, "IMAGE_REFERENCE": 78})
    assert novelty_count == 0
