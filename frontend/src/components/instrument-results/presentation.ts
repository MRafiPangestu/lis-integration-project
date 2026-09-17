// Pure presentation rules for XN-550 unlinked instrument results (G2).
// docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md Appendix C.
//
// Deliberately independent of the clinical `ResultFlag` mapping (which
// upper-cases values and knows words such as WARNING) and of the parser's
// observed-value sets. No React, no DOM: unit-tested with `node --test`.
import type { InstrumentResultItemResponse } from "../../types/api"

export const IDENTITY_NOTICE_CODE = "XN550_NO_VERIFIED_SPECIMEN_OR_PATIENT_IDENTIFIER"

// Contract C.2 / C.3 — the same persistent, non-dismissible text on both views.
export const IDENTITY_DISCLAIMER_TEXT =
  "Not linked to any patient record. The Sample No. is text typed on the instrument and is " +
  "not a verified patient or specimen identity. These results are not screened for QC " +
  "material, cannot be finalised and are not sent to SIMRS."

// Neutral caption for the shared date filter's "All" preset (contract C.1).
export const UNLINKED_ALL_DATES_CAPTION = "All dates · every unlinked result for this instrument"

export type FlagTone = "high" | "low" | "normal" | "unknown" | "none"

export interface FlagPresentation {
  tone: FlagTone
  symbol: string
  text: string
  accessibleLabel: string
}

// The ONLY known values: exact, case-sensitive single letters (ASTM E1394 codes).
const KNOWN_FLAGS: ReadonlyMap<string, { tone: FlagTone; symbol: string; meaning: string }> = new Map<
  string,
  { tone: FlagTone; symbol: string; meaning: string }
>([
  ["H", { tone: "high", symbol: "▲", meaning: "High" }],
  ["L", { tone: "low", symbol: "▼", meaning: "Low" }],
  ["N", { tone: "normal", symbol: "✓", meaning: "Normal" }],
])

export function presentInstrumentFlag(flag: string | null): FlagPresentation {
  if (flag === null || flag === "") {
    return { tone: "none", symbol: "—", text: "", accessibleLabel: "No instrument flag" }
  }
  const known = KNOWN_FLAGS.get(flag)
  if (known) {
    return {
      tone: known.tone,
      symbol: known.symbol,
      text: known.meaning,
      accessibleLabel: `Instrument flag ${flag}: ${known.meaning.toLowerCase()} (ASTM E1394 code)`,
    }
  }
  // Anything else — A, W, lower-case letters, words, values with spaces — is
  // unknown: shown verbatim, never mapped to a named state.
  return {
    tone: "unknown",
    symbol: "?",
    text: `${flag} — meaning not verified`,
    accessibleLabel: `Instrument flag ${flag}: meaning not verified`,
  }
}

export interface ItemGroup {
  kind: string
  title: string
  caption: string | null
  items: InstrumentResultItemResponse[]
}

const GROUP_ORDER: readonly { kind: string; title: string; caption: string | null }[] = [
  { kind: "MEASURED", title: "Measured parameters", caption: null },
  {
    kind: "INTERPRETIVE",
    title: "Instrument interpretive messages",
    caption: "Scores are shown verbatim — meaning not verified",
  },
  { kind: "FLAG_ONLY", title: "Instrument flags", caption: null },
]

export const IMAGE_REFERENCE_KIND = "IMAGE_REFERENCE"

// Keeps the API's item order within each group. Image references are returned
// separately (codes only). An unexpected kind stays visible, never hidden.
export function groupItemsByKind(items: readonly InstrumentResultItemResponse[]): ItemGroup[] {
  const groups: ItemGroup[] = []
  for (const group of GROUP_ORDER) {
    const members = items.filter((item) => item.item_kind === group.kind)
    if (members.length > 0) groups.push({ ...group, items: members })
  }
  const knownKinds = new Set([...GROUP_ORDER.map((group) => group.kind), IMAGE_REFERENCE_KIND])
  const other = items.filter((item) => !knownKinds.has(item.item_kind))
  if (other.length > 0) {
    groups.push({ kind: "OTHER", title: "Other instrument records", caption: "Shown verbatim", items: other })
  }
  return groups
}

export function imageReferenceCodes(items: readonly InstrumentResultItemResponse[]): string[] {
  return items.filter((item) => item.item_kind === IMAGE_REFERENCE_KIND).map((item) => item.test_code)
}

export function graphicsHeading(count: number): string {
  return `${count} ${count === 1 ? "graphic" : "graphics"} referenced on the instrument (not transferred)`
}

export function duplicateBadgeText(possibleDuplicateOf: number | null): string | null {
  if (possibleDuplicateOf === null) return null
  return `Possible duplicate of #${possibleDuplicateOf} — same content, not verified as the same analysis`
}

export function deliveryBadgeText(deliveryCount: number): string | null {
  return deliveryCount > 1 ? `Delivered ${deliveryCount}×` : null
}

// Server-local naive ISO timestamp -> "DD/MM/YYYY HH:MM:SS", without any time-zone
// conversion. An unexpected shape is shown verbatim.
export function formatNaiveDateTime(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(value)
  if (!match) return value
  const [, year, month, day, hour, minute, second] = match
  return `${day}/${month}/${year} ${hour}:${minute}:${second}`
}

export function displayOrDash(value: string | null): string {
  return value === null || value === "" ? "—" : value
}
