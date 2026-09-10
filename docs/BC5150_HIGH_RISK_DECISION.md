# BC-5150 HIGH-RISK Name-Passthrough — Decision Record

**Status:** Owner-approved, HIGH-RISK, interim operational decision. Active.
**Type:** Operational risk acceptance. This document authorises no source, schema,
migration, test or task-list change — those already landed in
`26b5396 feat(classification): add BC-5150 name passthrough`.
**Scope:** Mindray BC-5150 only.
**Governing evidence record:** `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` — that
document remains authoritative for all physical-message evidence and still records
(§9.5) that a positive **evidence-based** patient rule is **NOT APPROVED**.

---

## 1. Decision

The project owner has accepted the risk of running the BC-5150 under an explicit,
**unverified** name-based passthrough so that live patient results reach the
clinical pipeline and the frontend now, ahead of the field evidence that a proper
positive patient rule requires.

This is an **interim operational heuristic**, not a clinical or evidence
validation. It is opt-in per instrument and is **never** the default.

Classification policy: **`bc5150_name_passthrough`**

```
OBR-3 (stripped, casefolded) == "background"
    -> NON_PATIENT     / classification_rule = OBR3_BACKGROUND
else, PID-5 name populated
     (stripped, non-empty, and not the "UNKNOWN" sentinel, casefolded)
    -> PATIENT_RESULT  / classification_rule = BC5150_NAME_PASSTHROUGH
else (empty / whitespace-only / "UNKNOWN" PID-5)
    -> UNCLASSIFIED    / classification_rule = BC5150_NAME_ABSENT
```

## 2. What is verified vs. what is an owner decision

| Element | Basis |
|---|---|
| `OBR-3 == "Background"` → `NON_PATIENT` | **Field-verified evidence.** 27 historical + 2 live session-1 captures, no counter-example (`docs/09` §5.7, §18). Unchanged from `bc5150_field_verified`. |
| Named non-Background message → `PATIENT_RESULT` | **Owner-approved operational heuristic. NOT evidence-validated.** No field capture establishes that "a name in PID-5" identifies a patient run, or that its absence identifies a non-patient run. |
| Unnamed non-Background message → `UNCLASSIFIED` | Fail-closed default carried over from `bc5150_field_verified`. A non-Background message is **not** promoted merely by not matching "Background". |

## 3. Risk accepted

A QC, control, calibration or maintenance run that carries any name string in
PID-5 would be classified `PATIENT_RESULT` and persisted as a patient result
(Visit → Order → TestRun → Result). The BC-5150 QC/control message shape is
**UNKNOWN — zero captures** (`docs/09` §18, T-BC-K/L/M/N), so this misclassification
cannot currently be ruled out. The failure mode is asymmetric and clinical:
control-material values written into a patient record.

The owner has accepted this risk for the interim period.

## 4. Explicitly NOT solved by this decision

- **M9.3 (QC / Calibration Filtering Refinement)** remains **BLOCKED on field
  evidence** (`docs/09` §17). This decision does not implement QC filtering; it
  accepts the absence of it.
- **Positive evidence-based patient classification** remains **NOT APPROVED**
  (`docs/09` §9.5, §9.6). This policy is a separate operational choice, not a
  new evidence rule.
- **M9.2 (deduplication) / retransmission** is **not** proven. Under this policy
  patient messages now reach the exact-retransmission guard for the first time,
  but that guard has not been exercised against the physical device and no claim
  of correct dedup behaviour is made here.
- Live BC-5150 operation under this policy demonstrates only that the clinical
  pipeline *functions* end to end. It does **not** prove patient vs. QC semantics —
  that remains governed solely by `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md`.

## 5. Scope and activation

- **BC-5150 only.** No other instrument is affected. `resolve_policy(None)` still
  returns `strict`; other instruments keep their configured policy.
- **Explicit config only.** Activation is a single field in the (gitignored)
  `backend/instruments.json`:
  `"classification_policy": "bc5150_name_passthrough"`.
- **Never the default.** The tracked template `backend/instruments.example.json`
  stays at `bc5150_field_verified`, so a fresh deployment is fail-closed and
  enabling this policy is a deliberate per-deployment act.

## 6. Rollback

Set the BC-5150 `classification_policy` in `backend/instruments.json` back to:

```
bc5150_field_verified
```

and restart the integration service. No migration, schema change or data backfill
is involved; the change is classification-only and takes effect for messages
received after restart. Rows already persisted under
`BC5150_NAME_PASSTHROUGH` remain and are auditable by that `classification_rule`
token.

## 7. Exit condition

Replace this heuristic once a physical QC/control session (T-BC-K ×2 on different
days, plus T-BC-A across ≥3 distinct patients and T-BC-H — `docs/09` §9.5, §16
step 6) produces evidence that establishes a **positive patient discriminator**.
At that point `bc5150_name_passthrough` is retired in favour of an
evidence-based policy and this record is closed.
