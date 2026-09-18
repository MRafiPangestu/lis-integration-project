// Instrument status presentation — one operator-facing answer, plus detail.
//
// The API returns two values with two distinct jobs (backend
// app/integration/instrument_status.py):
//
//   connection_status           transport / runtime state of the integration
//                               worker. Mode-specific: only a listener-mode
//                               instrument ever reports LISTENING.
//   instrument_connection_state the operator-facing answer to "is there an
//                               active session with the instrument?"
//
// The primary label always comes from the connection state, so a Sysmex
// XN-550 sitting on an idle listener and a Mindray BC-5150 failing to dial
// both read "Disconnected" — same physical reality, same word. The transport
// state becomes secondary detail, which is where LISTENING and RECONNECTING
// still earn their keep.
//
// Pure: no React, no DOM. Unit-tested with `node --test`.

export type ConnectionTone = "connected" | "disconnected" | "unknown"

export interface InstrumentStatusPresentation {
  /** Operator-facing primary label. Never mode-specific. */
  primary: string
  /** Transport/runtime detail, or null when it would only repeat the primary. */
  detail: string | null
  tone: ConnectionTone
  /** Design-system colour token for the status dot. */
  color: string
  /** One-line form for `title` / `aria-label`. */
  summary: string
}

const PRIMARY_LABELS: Readonly<Record<string, string>> = {
  CONNECTED: "Connected",
  DISCONNECTED: "Disconnected",
  UNKNOWN: "Unknown",
}

// Only states that add something the primary label does not already say.
// CONNECTED is deliberately absent: "Connected · Connected" is noise.
const TRANSPORT_DETAILS: Readonly<Record<string, string>> = {
  LISTENING: "Listener ready — no instrument session",
  RECONNECTING: "Reconnecting…",
  DISCONNECTED: "Integration service stopped",
  UNKNOWN: "No status reported yet",
}

const TONE_COLORS: Readonly<Record<ConnectionTone, string>> = {
  connected: "var(--color-flag-normal)",
  disconnected: "var(--color-flag-low)",
  unknown: "var(--color-text-secondary)",
}

function normalize(value: string | null | undefined): string {
  return (value ?? "").trim().toUpperCase()
}

function toneFor(connectionState: string): ConnectionTone {
  if (connectionState === "CONNECTED") return "connected"
  if (connectionState === "DISCONNECTED") return "disconnected"
  return "unknown"
}

export function presentInstrumentStatus(
  connectionState: string | null | undefined,
  transportState: string | null | undefined,
): InstrumentStatusPresentation {
  const connection = normalize(connectionState)
  const transport = normalize(transportState)

  // An unrecognised or missing connection state falls back to Unknown. It must
  // never read as connected.
  const known = connection in PRIMARY_LABELS ? connection : "UNKNOWN"
  const tone = toneFor(known)
  const primary = PRIMARY_LABELS[known]
  const detail = TRANSPORT_DETAILS[transport] ?? null

  return {
    primary,
    detail,
    tone,
    color: TONE_COLORS[tone],
    summary: detail === null ? primary : `${primary} · ${detail}`,
  }
}
