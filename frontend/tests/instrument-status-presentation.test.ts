import assert from "node:assert/strict"
import test from "node:test"

import { presentInstrumentStatus } from "../src/components/layout/instrumentStatus.ts"

test("an active session reads Connected with no redundant detail", () => {
  const p = presentInstrumentStatus("CONNECTED", "CONNECTED")
  assert.equal(p.primary, "Connected")
  assert.equal(p.tone, "connected")
  assert.equal(p.detail, null, "Connected · Connected would be noise")
  assert.equal(p.summary, "Connected")
})

test("listener mode with no session reads Disconnected, with the listener as detail", () => {
  const p = presentInstrumentStatus("DISCONNECTED", "LISTENING")
  assert.equal(p.primary, "Disconnected")
  assert.equal(p.tone, "disconnected")
  assert.equal(p.detail, "Listener ready — no instrument session")
  assert.equal(p.summary, "Disconnected · Listener ready — no instrument session")
})

test("client mode retrying reads Disconnected, with the retry as detail", () => {
  const p = presentInstrumentStatus("DISCONNECTED", "RECONNECTING")
  assert.equal(p.primary, "Disconnected")
  assert.equal(p.tone, "disconnected")
  assert.equal(p.detail, "Reconnecting…")
})

test("the operator sees the same primary word for both transport modes", () => {
  // The whole point: a listener sitting idle and a client failing to dial are
  // the same thing to the person looking at the screen.
  const xn550 = presentInstrumentStatus("DISCONNECTED", "LISTENING")
  const bc5150 = presentInstrumentStatus("DISCONNECTED", "RECONNECTING")

  assert.equal(xn550.primary, bc5150.primary)
  assert.equal(xn550.tone, bc5150.tone)
  assert.equal(xn550.color, bc5150.color)
  assert.notEqual(xn550.detail, bc5150.detail, "but the reason is still distinguishable")
})

test("a stopped integration service is Disconnected with its own detail", () => {
  const p = presentInstrumentStatus("DISCONNECTED", "DISCONNECTED")
  assert.equal(p.primary, "Disconnected")
  assert.equal(p.detail, "Integration service stopped")
})

test("never-reported instruments read Unknown, not Connected", () => {
  for (const [connection, transport] of [
    ["UNKNOWN", "UNKNOWN"],
    [null, null],
    [undefined, undefined],
    ["", ""],
  ] as const) {
    const p = presentInstrumentStatus(connection, transport)
    assert.equal(p.primary, "Unknown")
    assert.equal(p.tone, "unknown")
    assert.notEqual(p.tone, "connected")
  }
})

test("an unrecognised connection state falls back to Unknown rather than Connected", () => {
  const p = presentInstrumentStatus("BANANA", "BANANA")
  assert.equal(p.primary, "Unknown")
  assert.equal(p.tone, "unknown")
  assert.equal(p.detail, null, "an unrecognised transport state contributes no detail")
})

test("casing and whitespace from the API do not change the answer", () => {
  const p = presentInstrumentStatus(" connected ", " listening ")
  assert.equal(p.primary, "Connected")
  assert.equal(p.tone, "connected")
})

test("each tone maps to a distinct design-system token", () => {
  const connected = presentInstrumentStatus("CONNECTED", "CONNECTED").color
  const disconnected = presentInstrumentStatus("DISCONNECTED", "LISTENING").color
  const unknown = presentInstrumentStatus("UNKNOWN", "UNKNOWN").color

  assert.equal(new Set([connected, disconnected, unknown]).size, 3)
  for (const color of [connected, disconnected, unknown]) {
    assert.match(color, /^var\(--color-/, "colours must come from the design system")
  }
})
