"""ASTM E1394 byte-stream handling for listener-mode instruments.

Transport-independent and database-free. Currently holds only the CR-record
message assembler used by XN-550 Phase 1 raw capture; an E1381 de-framing layer,
if field evidence ever requires one, belongs below the assembler as a separate
module (docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md §5.8).
"""
