"""Parser registry (M8.3).

An explicit, static mapping from a configuration ``parser_key`` to a concrete
parser.

Pure parser-layer module: no database, no session, no runtime-instrument
objects, no dynamic import machinery. Resolution is an exact dictionary lookup.

An unknown key raises :class:`ParserNotRegisteredError` — there is deliberately
**no fallback** and **no case-insensitive / fuzzy matching**, because binding a
message to the wrong parser can produce plausible-but-incorrect clinical data.
Parser resolution therefore fails closed by failing loudly.

Each key also has an explicit protocol family (XN-550 contract §19.1), so that
startup can refuse to bind an ASTM parser to the HL7/MLLP client path or the HL7
parser to a listener:

* ``bc5150_hl7`` — ``HL7_MLLP``: ``str -> Optional[ParsedHL7]``;
* ``xn550_astm_e1394`` — ``ASTM_E1394_CR``: ``bytes -> AstmParseResult``. It is
  the dedicated Sysmex XN-550 parser, not a generic ASTM parser.
"""
from __future__ import annotations

from typing import Callable, Union

from app.integration.parsers import ParserFn
from app.integration.parsers.hl7 import parse_hl7_bc5150
from app.integration.parsers.xn550_astm import AstmParseResult, parse_xn550_astm


class ParserNotRegisteredError(RuntimeError):
    """Raised when a configured ``parser_key`` has no registered parser."""


PROTOCOL_HL7_MLLP = "HL7_MLLP"
PROTOCOL_ASTM_E1394_CR = "ASTM_E1394_CR"

RegisteredParser = Union[ParserFn, Callable[[bytes], AstmParseResult]]

_PARSERS: "dict[str, RegisteredParser]" = {
    "bc5150_hl7": parse_hl7_bc5150,
    "xn550_astm_e1394": parse_xn550_astm,
}

_PROTOCOL_FAMILIES: "dict[str, str]" = {
    "bc5150_hl7": PROTOCOL_HL7_MLLP,
    "xn550_astm_e1394": PROTOCOL_ASTM_E1394_CR,
}

KNOWN_PARSER_KEYS = frozenset(_PARSERS)

if frozenset(_PROTOCOL_FAMILIES) != KNOWN_PARSER_KEYS:  # pragma: no cover - static invariant
    raise RuntimeError("every registered parser key must declare exactly one protocol family")


def resolve_parser(parser_key: str) -> RegisteredParser:
    """Return the parser registered under ``parser_key`` (exact match only).

    Raises :class:`ParserNotRegisteredError` for any unknown key: no fallback,
    no fuzzy or case-insensitive matching.
    """
    try:
        return _PARSERS[parser_key]
    except KeyError:
        raise ParserNotRegisteredError(
            f"No parser registered for parser_key {parser_key!r}. "
            f"Known parser keys: {sorted(KNOWN_PARSER_KEYS)}."
        ) from None


def protocol_family(parser_key: str) -> str:
    """Return the protocol family of a registered key (exact match only).

    Raises :class:`ParserNotRegisteredError` for any unknown key, exactly like
    :func:`resolve_parser`.
    """
    try:
        return _PROTOCOL_FAMILIES[parser_key]
    except KeyError:
        raise ParserNotRegisteredError(
            f"No parser registered for parser_key {parser_key!r}. "
            f"Known parser keys: {sorted(KNOWN_PARSER_KEYS)}."
        ) from None
