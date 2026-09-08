"""Parser registry (M8.3).

An explicit, static mapping from a configuration ``parser_key`` to a concrete
:data:`~app.integration.parsers.ParserFn`.

Pure parser-layer module: no database, no session, no runtime-instrument
objects, no dynamic import machinery. Resolution is an exact dictionary lookup.

An unknown key raises :class:`ParserNotRegisteredError` — there is deliberately
**no fallback** and **no case-insensitive / fuzzy matching**, because binding a
message to the wrong parser can produce plausible-but-incorrect clinical data.
Parser resolution therefore fails closed by failing loudly.
"""
from __future__ import annotations

from app.integration.parsers import ParserFn
from app.integration.parsers.hl7 import parse_hl7_bc5150


class ParserNotRegisteredError(RuntimeError):
    """Raised when a configured ``parser_key`` has no registered parser."""


_PARSERS: "dict[str, ParserFn]" = {
    "bc5150_hl7": parse_hl7_bc5150,
}

KNOWN_PARSER_KEYS = frozenset(_PARSERS)


def resolve_parser(parser_key: str) -> ParserFn:
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
