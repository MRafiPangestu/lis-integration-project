"""XN-550 T2 classification stage for G1 ``raw_only`` (XN-550 Phase 2).

Runs after the Phase-1 T1 commit (contract §9.3) and implements the G1 part of
§10.4: parse the **authoritative ``raw_bytes``** of one ``Pending`` raw message,
apply the ``xn550_observed_envelope`` policy, and write the outcome back to that
same ``instrument_messages`` row. Nothing else.

It never creates observation rows (G2), never touches Patient / Visit / Order /
TestRun / Result, never writes ``audit_events``, never links duplicates and never
classifies anything as ``PATIENT_RESULT``. ``raw_message`` is not read.

Logs and ``error_detail`` carry stable tokens, record indices, field numbers,
message ids and exception type names only — never payload text.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.integration.astm.assembler import FRAMING_ASTM_CR_RECORDS
from app.integration.classification import MessageClass
from app.integration.parsers.xn550_astm import (
    AstmParseResult,
    ConformantMessage,
    Unparseable,
    ensure_not_patient_result,
    error_detail_for,
)
from app.integration.raw_capture import PARSE_STATUS_FAILED, PARSE_STATUS_PENDING, sha256_hex
from app.models import InstrumentMessage

log = logging.getLogger(__name__)

PARSE_STATUS_SUCCESS = "Success"

TOKEN_T2_EXCEPTION = "XN550_T2_EXCEPTION"
TOKEN_RAW_INTEGRITY_MISMATCH = "XN550_RAW_INTEGRITY_MISMATCH"

ParserFn = Callable[[bytes], AstmParseResult]
PolicyFn = Callable[[AstmParseResult], "object"]


class Xn550ClassificationStage:
    """Classify persisted XN-550 raw messages in place. One instance per instrument."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        parser: ParserFn,
        policy: PolicyFn,
        parser_key: str,
        parser_version: str,
    ) -> None:
        self._session_factory = session_factory
        self._parser = parser
        self._policy = policy
        self._parser_key = parser_key
        self._parser_version = parser_version

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
            row = session.get(InstrumentMessage, id_message)
            if (
                row is None
                or row.parse_status != PARSE_STATUS_PENDING
                or row.framing != FRAMING_ASTM_CR_RECORDS
                or row.raw_bytes is None
            ):
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
            session.commit()

        if isinstance(result, ConformantMessage):
            log.info(
                "xn550 T2: message %s %s (%d result records)",
                id_message, classification.classification_rule, len(result.results),
            )
            for novelty in result.novelties:
                log.warning(
                    "xn550 T2: message %s %s @record %s field %s",
                    id_message, novelty.token, novelty.record_index, novelty.field_number,
                )
        else:
            log.warning("xn550 T2: message %s %s", id_message, error_detail_for(result))
        return classification.classification_rule

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
