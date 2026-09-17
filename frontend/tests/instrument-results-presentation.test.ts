// XN-550 unlinked instrument results — presentation rules (contract Appendix C).
// Run with: npm test   (node --experimental-strip-types --test)
import assert from "node:assert/strict"
import { test } from "node:test"

import {
  IDENTITY_DISCLAIMER_TEXT,
  IDENTITY_NOTICE_CODE,
  UNLINKED_ALL_DATES_CAPTION,
  deliveryBadgeText,
  displayOrDash,
  duplicateBadgeText,
  formatNaiveDateTime,
  graphicsHeading,
  groupItemsByKind,
  imageReferenceCodes,
  presentInstrumentFlag,
} from "../src/components/instrument-results/presentation.ts"

test("exact H / L / N render as High / Low / Normal", () => {
  assert.deepEqual(
    ["H", "L", "N"].map((flag) => [presentInstrumentFlag(flag).tone, presentInstrumentFlag(flag).text]),
    [["high", "High"], ["low", "Low"], ["normal", "Normal"]],
  )
  assert.equal(presentInstrumentFlag("H").symbol, "▲")
  assert.equal(presentInstrumentFlag("L").symbol, "▼")
  assert.equal(presentInstrumentFlag("N").symbol, "✓")
})

test("A and W, and any other non-empty value, render as unknown with the verbatim value", () => {
  for (const flag of ["A", "W", "h", "l", "n", "HIGH", "LOW", "NORMAL", "WARNING", "CRITICAL", " H", "N ", "HH", "?"]) {
    const presentation = presentInstrumentFlag(flag)
    assert.equal(presentation.tone, "unknown", flag)
    assert.equal(presentation.symbol, "?", flag)
    assert.equal(presentation.text, `${flag} — meaning not verified`, flag)
    assert.equal(presentation.accessibleLabel, `Instrument flag ${flag}: meaning not verified`, flag)
  }
})

test("empty or missing flag renders as a dash", () => {
  for (const flag of [null, ""]) {
    const presentation = presentInstrumentFlag(flag)
    assert.deepEqual([presentation.tone, presentation.symbol, presentation.text], ["none", "—", ""])
  }
})

test("the identity disclaimer text is the contract text", () => {
  assert.equal(
    IDENTITY_DISCLAIMER_TEXT,
    "Not linked to any patient record. The Sample No. is text typed on the instrument and is not a verified " +
      "patient or specimen identity. These results are not screened for QC material, cannot be finalised and " +
      "are not sent to SIMRS.",
  )
  assert.equal(IDENTITY_NOTICE_CODE, "XN550_NO_VERIFIED_SPECIMEN_OR_PATIENT_IDENTIFIER")
  assert.ok(!UNLINKED_ALL_DATES_CAPTION.toLowerCase().includes("order"))
})

const item = (r_sequence: number, test_code: string, item_kind: string, value: string | null, abnormal_flag: string | null) => ({
  r_sequence,
  test_code,
  item_kind,
  value,
  units: null,
  reference_range: null,
  abnormal_flag,
  result_status: "F",
})

test("items are grouped by kind in contract order, interpretive scores stay verbatim, images are codes only", () => {
  const items = [
    item(1, "WBC", "MEASURED", "11.30", "N"),
    item(2, "Blasts/Abn_Lympho?", "INTERPRETIVE", "30", null),
    item(3, "IG_Present", "FLAG_ONLY", null, "A"),
    item(4, "SCAT_WDF", "IMAGE_REFERENCE", null, "N"),
    item(5, "RBC", "MEASURED", "4.75", "W"),
  ]
  const groups = groupItemsByKind(items)
  assert.deepEqual(groups.map((group) => group.kind), ["MEASURED", "INTERPRETIVE", "FLAG_ONLY"])
  assert.deepEqual(groups[0].items.map((entry) => entry.test_code), ["WBC", "RBC"])
  assert.equal(groups[1].items[0].value, "30")
  assert.match(groups[1].caption ?? "", /meaning not verified/)
  assert.deepEqual(imageReferenceCodes(items), ["SCAT_WDF"])
  assert.equal(graphicsHeading(1), "1 graphic referenced on the instrument (not transferred)")
  assert.equal(graphicsHeading(4), "4 graphics referenced on the instrument (not transferred)")
})

test("an unexpected item kind stays visible", () => {
  const groups = groupItemsByKind([item(1, "X", "NEW_KIND", "1", null)])
  assert.deepEqual(groups.map((group) => group.kind), ["OTHER"])
})

test("duplicate and delivery badges", () => {
  assert.equal(duplicateBadgeText(null), null)
  assert.equal(duplicateBadgeText(7), "Possible duplicate of #7 — same content, not verified as the same analysis")
  assert.equal(deliveryBadgeText(1), null)
  assert.equal(deliveryBadgeText(3), "Delivered 3×")
})

test("naive timestamps are formatted without any time-zone conversion", () => {
  assert.equal(formatNaiveDateTime("2026-09-15T02:32:25"), "15/09/2026 02:32:25")
  assert.equal(formatNaiveDateTime("2026-09-15T23:59:59.123456"), "15/09/2026 23:59:59")
  assert.equal(formatNaiveDateTime("not a date"), "not a date")
  assert.equal(displayOrDash(null), "—")
  assert.equal(displayOrDash(""), "—")
  assert.equal(displayOrDash("10*3/uL"), "10*3/uL")
})
