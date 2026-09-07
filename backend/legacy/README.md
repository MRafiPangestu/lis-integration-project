# Legacy integration code (reference only)

These files predate the ORM refactor and are **superseded by `backend/app/`**:

| File | Superseded by |
|---|---|
| `alt_server.py` | `app/integration/client.py` + `app/integration/repository.py` + `run_integration.py` |
| `lis_server.py` | same as above |
| `api.py` | `app/main.py` + `app/api/` |
| `hl7_parser.py` | `app/integration/parsers/hl7.py` |

## Rules

- **Do not run these as the active integration service or API.** They are kept
  for proof-of-concept and behavioural/regression reference only.
- They contain stale, pre-refactor assumptions: the old flat `results.id_order`
  schema, `ON CONFLICT DO UPDATE` upserts, a hardcoded `id_instrument = 2`, and
  raw `psycopg2` access.
- They may contain **sensitive or stale hardcoded configuration** (database
  credentials, instrument IP/port) and must not be executed as production code.

## Historical endpoint evidence

`alt_server.py` and `lis_server.py` connected to the physical Mindray BC-5150 at
`10.0.0.2:5100` during the PoC. Treat this as a *previously working / historically
verified* endpoint only — it is **not** confirmed as the current production
endpoint and must be re-verified against the physical instrument before use.
Local development and regression testing use `127.0.0.1:5100` with the simulator.

## Preserved sample

`hl7_parser.py` embeds a real BC-5150 HL7 capture in its `__main__` block. Keep
this file for that capture; it is regression evidence for the active parser.
