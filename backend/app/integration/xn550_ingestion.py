"""XN-550 T2 stage: classification, byte-identity linking and G2 observations.

Runs after the Phase-1 T1 commit (contract §9.3) and implements
docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md §10.4:

* **Every** T2 transaction takes the per-instrument advisory lock first (§14.2),
  re-reads its row ``FOR UPDATE`` and processes it only while ``Pending``.
* It parses the **authoritative ``raw_bytes``**, applies the
  ``xn550_observed_envelope`` policy and writes the outcome back to the row.
* For envelope-conformant rows, in **both** ingestion stages, it links a
  byte-identical redelivery to the lowest-id earlier member of its delivery
  group (§13.2).
* In stage ``observations`` only (G2), it creates one unlinked result set with
  its items, unless a byte-identical delivery already owns one, and flags
  possible duplicates (§13.3).

It never touches Patient / Visit / Order / TestRun / Result, never writes
``audit_events``, never classifies anything as ``PATIENT_RESULT``, never reads
``raw_message`` and never updates a row that has left ``Pending`` (no backfill).

Logs and ``error_detail`` carry stable tokens, record indices, field numbers,
ids, counts and exception type names only — never payload text.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.integration.astm.assembler import FRAMING_ASTM_CR_RECORDS
from app.integration.classification import MessageClass
from app.integration.parsers.xn550_astm import (
    RULE_ENVELOPE_CONFORMANT,
    AstmParseResult,
    ConformantMessage,
    Unparseable,
    ensure_not_patient_result,
    error_detail_for,
)
from app.integration.raw_capture import PARSE_STATUS_FAILED, PARSE_STATUS_PENDING, sha256_hex
from app.integration.xn550_normalize import (
    FINGERPRINT_VERSION,
    analysis_fingerprint_v1,
    normalize_xn550,
    resolve_identity,
)
from app.integration.xn550_observations import (
    byte_identical_root,
    earliest_same_fingerprint,
    group_owns_result_set,
    insert_result_set,
    lock_instrument,
    redelivery_note,
)
from app.models import InstrumentMessage

log = logging.getLogger(__name__)

PARSE_STATUS_SUCCESS = "Success"

TOKEN_T2_EXCEPTION = "XN550_T2_EXCEPTION"
TOKEN_RAW_INTEGRITY_MISMATCH = "XN550_RAW_INTEGRITY_MISMATCH"

INGESTION_STAGE_RAW_ONLY = "raw_only"
INGESTION_STAGE_OBSERVATIONS = "observations"
INGESTION_STAGES = frozenset({INGESTION_STAGE_RAW_ONLY, INGESTION_STAGE_OBSERVATIONS})

ParserFn = Callable[[bytes], AstmParseResult]
PolicyFn = Callable[[AstmParseResult], "object"]


@dataclass(frozen=True)
class _ObservationOutcome:
    linked_to: Optional[int] = None
    id_result_set: Optional[int] = None
    duplicate_status: Optional[str] = None
    set_owned_by_group: bool = False


class Xn550ClassificationStage:
    """Classify persisted XN-550 raw messages in place and, in G2, create observations.

    One instance per instrument. ``ingestion_stage`` defaults to ``raw_only``
    (G1); only an explicit ``observations`` creates result sets.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        parser: ParserFn,
        policy: PolicyFn,
        parser_key: str,
        parser_version: str,
        ingestion_stage: str = INGESTION_STAGE_RAW_ONLY,
    ) -> None:
        if ingestion_stage not in INGESTION_STAGES:
            raise ValueError(f"unknown XN-550 ingestion_stage {ingestion_stage!r}")
        self._session_factory = session_factory
        self._parser = parser
        self._policy = policy
        self._parser_key = parser_key
        self._parser_version = parser_version
        self._ingestion_stage = ingestion_stage

    @property
    def ingestion_stage(self) -> str:
        return self._ingestion_stage

    # -- hooks used by the listener ------------------------------------------------

    def process(self, id_message: int) -> Optional[str]:
        """Classify one raw message. Never raises.

        Returns the ``classification_rule`` written, or ``None`` when the row is
        not a pending XN-550 raw-capture row (already processed, missing, or not
        raw capture) and was left untouched.
        """
        try:
            return self._process(id_message)
        except Exception as exc:
            log.error(
                "xn550 T2: message %s classification failed (%s); recording %s",
                id_message, type(exc).__name__, TOKEN_T2_EXCEPTION,
            )
            self._record_exception(id_message)
            return TOKEN_T2_EXCEPTION

    def process_pending(self, id_instrument: int) -> int:
        """Classify every still-``Pending`` raw-capture row of *id_instrument*, in id order.

        Rows stay ``Pending`` when a crash or outage happened between T1 and T2
        (contract §14.2). Returns the number of rows attempted.
        """
        with self._session_factory() as session:
            ids = session.scalars(
                select(InstrumentMessage.id_message)
                .where(
                    InstrumentMessage.id_instrument == id_instrument,
                    InstrumentMessage.parse_status == PARSE_STATUS_PENDING,
                    InstrumentMessage.framing == FRAMING_ASTM_CR_RECORDS,
                    InstrumentMessage.raw_bytes.is_not(None),
                )
                .order_by(InstrumentMessage.id_message)
            ).all()
        for id_message in ids:
            self.process(id_message)
        if ids:
            log.info("xn550 T2: processed %d pending raw message(s) for instrument %s", len(ids), id_instrument)
        return len(ids)

    # -- internals ------------------------------------------------------------------------

    def _process(self, id_message: int) -> Optional[str]:
        with self._session_factory() as session:
            id_instrument = session.scalar(
                select(InstrumentMessage.id_instrument).where(InstrumentMessage.id_message == id_message)
            )
            if id_instrument is None:
                return None

            # §10.4 step 0: serialise per instrument, then re-read the row under a row lock.
            lock_instrument(session, id_instrument)
            row = session.scalars(
                select(InstrumentMessage)
                .where(InstrumentMessage.id_message == id_message)
                .with_for_update()
            ).one_or_none()
            if (
                row is None
                or row.parse_status != PARSE_STATUS_PENDING
                or row.framing != FRAMING_ASTM_CR_RECORDS
                or row.raw_bytes is None
            ):
                session.rollback()
                return None

            raw = bytes(row.raw_bytes)
            row.parser_key = self._parser_key
            if row.raw_sha256 != sha256_hex(raw) or row.raw_length != len(raw):
                row.parser_version = self._parser_version
                row.parse_status = PARSE_STATUS_FAILED
                row.message_class = MessageClass.UNPARSEABLE.value
                row.classification_rule = TOKEN_RAW_INTEGRITY_MISMATCH
                row.error_detail = TOKEN_RAW_INTEGRITY_MISMATCH
                session.commit()
                log.error("xn550 T2: message %s %s", id_message, TOKEN_RAW_INTEGRITY_MISMATCH)
                return TOKEN_RAW_INTEGRITY_MISMATCH

            result = self._parser(raw)
            classification = ensure_not_patient_result(self._policy(result))

            row.parser_version = result.parser_version
            row.message_class = classification.message_class.value
            row.classification_rule = classification.classification_rule
            row.error_detail = error_detail_for(result)
            row.parse_status = (
                PARSE_STATUS_FAILED if isinstance(result, Unparseable) else PARSE_STATUS_SUCCESS
            )

            outcome = _ObservationOutcome()
            conformant = (
                isinstance(result, ConformantMessage)
                and classification.classification_rule == RULE_ENVELOPE_CONFORMANT
            )
            if conformant:
                outcome = self._link_and_observe(session, row, result)
            session.commit()

        self._log_outcome(id_message, result, classification.classification_rule, outcome)
        return classification.classification_rule

    def _link_and_observe(
        self, session: Session, row: InstrumentMessage, result: ConformantMessage
    ) -> _ObservationOutcome:
        root = byte_identical_root(session, row.id_instrument, row.raw_sha256, row.id_message)
        if root is not None:
            row.duplicate_of_message_id = root
            row.error_detail = redelivery_note(root)

        if self._ingestion_stage != INGESTION_STAGE_OBSERVATIONS:
            return _ObservationOutcome(linked_to=root)
        if group_owns_result_set(session, row.id_instrument, row.raw_sha256):
            return _ObservationOutcome(linked_to=root, set_owned_by_group=True)

        normalized = normalize_xn550(result)
        fingerprint = analysis_fingerprint_v1(row.id_instrument, normalized)
        earlier = earliest_same_fingerprint(session, row.id_instrument, FINGERPRINT_VERSION, fingerprint)
        result_set = insert_result_set(
            session,
            message=row,
            normalized=normalized,
            fingerprint=fingerprint,
            possible_duplicate_of=earlier,
            identity=resolve_identity(normalized),
        )
        return _ObservationOutcome(
            linked_to=root,
            id_result_set=result_set.id_result_set,
            duplicate_status=result_set.duplicate_status,
        )

    def _log_outcome(
        self,
        id_message: int,
        result: AstmParseResult,
        classification_rule: str,
        outcome: _ObservationOutcome,
    ) -> None:
        if not isinstance(result, ConformantMessage):
            log.warning("xn550 T2: message %s %s", id_message, error_detail_for(result))
            return
        log.info(
            "xn550 T2: message %s %s (%d result records)",
            id_message, classification_rule, len(result.results),
        )
        if outcome.linked_to is not None:
            log.info("xn550 T2: message %s is a byte-identical redelivery of message %s", id_message, outcome.linked_to)
        if outcome.id_result_set is not None:
            log.info(
                "xn550 T2: message %s created unlinked result set %s (%s)",
                id_message, outcome.id_result_set, outcome.duplicate_status,
            )
        elif outcome.set_owned_by_group:
            log.info("xn550 T2: message %s creates no result set; its delivery group already owns one", id_message)
        for novelty in result.novelties:
            log.warning(
                "xn550 T2: message %s %s @record %s field %s",
                id_message, novelty.token, novelty.record_index, novelty.field_number,
            )

    def _record_exception(self, id_message: int) -> None:
        """T3: record the failure on the T1 row, only if it is still Pending."""
        try:
            with self._session_factory() as session:
                session.execute(
                    update(InstrumentMessage)
                    .where(
                        InstrumentMessage.id_message == id_message,
                        InstrumentMessage.parse_status == PARSE_STATUS_PENDING,
                    )
                    .values(
                        parse_status=PARSE_STATUS_FAILED,
                        message_class=MessageClass.UNPARSEABLE.value,
                        classification_rule=TOKEN_T2_EXCEPTION,
                        error_detail=TOKEN_T2_EXCEPTION,
                        parser_key=self._parser_key,
                        parser_version=self._parser_version,
                    )
                )
                session.commit()
        except Exception as exc:
            log.error(
                "xn550 T2: could not record %s for message %s (%s); row stays Pending",
                TOKEN_T2_EXCEPTION, id_message, type(exc).__name__,
            )
