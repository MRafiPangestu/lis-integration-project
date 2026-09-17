// XN-550 unlinked instrument results — static identity-boundary checks on the
// frontend source (contract §12.3, Appendix C.1 and C.4). No DOM needed.
import assert from "node:assert/strict"
import { readdirSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { test } from "node:test"
import { fileURLToPath } from "node:url"

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src")
const VIEW_DIR = join(SRC, "components", "instrument-results")
const read = (...parts: string[]) => readFileSync(join(SRC, ...parts), "utf8")

// The checks look at code, not at explanatory comments.
function stripComments(source: string): string {
  return source
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
}

const viewFiles = readdirSync(VIEW_DIR).filter((name) => name.endsWith(".ts") || name.endsWith(".tsx"))
const guardedSources: [string, string][] = [
  ...viewFiles.map((name): [string, string] => [name, stripComments(readFileSync(join(VIEW_DIR, name), "utf8"))]),
  ["hooks/useInstrumentResults.ts", stripComments(read("hooks", "useInstrumentResults.ts"))],
  ["hooks/useInstrumentResult.ts", stripComments(read("hooks", "useInstrumentResult.ts"))],
]

const FORBIDDEN_COMPONENTS = [
  "ResultTable", "ResultRow", "ResultFlag", "PatientSummary", "VisitOrderSelector", "TestRunSelector",
  "OrderOverviewView", "OrderOverviewTable", "OrderOverviewRow", "OverviewHeader", "OrderDetailView",
  "FilterBar", "MainLayout", "FinalRunWorkflow", "SimrsSyncWorkflow", "ConfirmationDialog",
]
const FORBIDDEN_TYPES = [
  "ResultResponse", "TestRunResponse", "PatientResponse", "VisitResponse", "OrderResponse",
  "HistoryPatientResponse", "FlatResultResponse", "OrderOverviewRow",
]

function importedNames(source: string): string[] {
  const names: string[] = []
  for (const match of source.matchAll(/import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+"([^"]+)"/g)) {
    names.push(...match[1].split(",").map((name) => name.replace(/\btype\b/, "").trim()).filter(Boolean))
    names.push(match[2])
  }
  for (const match of source.matchAll(/import\s+(\w+)\s+from\s+"([^"]+)"/g)) {
    names.push(match[1], match[2])
  }
  return names
}

test("the XN-550 views import no clinical component or clinical type", () => {
  assert.ok(viewFiles.length >= 5)
  for (const [name, source] of guardedSources) {
    const imported = importedNames(source)
    for (const forbidden of [...FORBIDDEN_COMPONENTS, ...FORBIDDEN_TYPES]) {
      assert.ok(
        !imported.some((entry) => entry === forbidden || entry.endsWith(`/${forbidden}`)),
        `${name} imports ${forbidden}`,
      )
    }
    for (const forbiddenPath of ["/display/", "/detail/", "/workflow/", "layout/FilterBar", "layout/MainLayout"]) {
      assert.ok(!imported.some((entry) => entry.includes(forbiddenPath)), `${name} imports from ${forbiddenPath}`)
    }
  }
})

test("no search, no Sample No. filter and no free-text input in the XN-550 views", () => {
  for (const [name, source] of guardedSources) {
    assert.ok(!/search/i.test(source), `${name} mentions search`)
    assert.ok(!/<input\b/.test(source), `${name} renders an input`)
    assert.ok(!/<textarea\b|<select\b|<form\b/.test(source), `${name} renders a form control`)
  }
})

test("r_sequence is never rendered", () => {
  for (const [name, source] of guardedSources) {
    assert.ok(!source.includes("r_sequence"), `${name} references r_sequence`)
    assert.ok(!/\bSeq\b/.test(source), `${name} shows a "Seq" label`)
  }
})

test("both views render the persistent identity disclaimer and are not a patient worklist", () => {
  for (const view of ["InstrumentResultsListView.tsx", "InstrumentResultDetailView.tsx"]) {
    const source = stripComments(readFileSync(join(VIEW_DIR, view), "utf8"))
    assert.match(source, /<IdentityDisclaimer\b/, view)
    assert.ok(!/worklist|Patient<\/th>|nomor_rm|no_registrasi|nama_lengkap/i.test(source), view)
  }
  const disclaimer = stripComments(readFileSync(join(VIEW_DIR, "IdentityDisclaimer.tsx"), "utf8"))
  assert.ok(!/onClose|dismiss|setVisible|useState/.test(disclaimer), "the disclaimer must not be dismissible")
})

test("the XN-550 data layer is read-only and the flag mapping is not the clinical one", () => {
  const hooks = read("hooks", "useInstrumentResults.ts") + read("hooks", "useInstrumentResult.ts")
  assert.ok(!/apiClient\.(post|put|patch|delete)/.test(hooks))
  const endpoints = read("api", "endpoints.ts")
  const xn550Section = endpoints.slice(endpoints.indexOf("export function getInstrumentResults"))
  assert.ok(xn550Section.includes("apiClient.get"))
  assert.ok(!/apiClient\.(post|put|patch|delete)/.test(xn550Section))
  const presentation = stripComments(readFileSync(join(VIEW_DIR, "presentation.ts"), "utf8"))
  assert.ok(!/toUpperCase|WARNING|CRITICAL/.test(presentation))
})

test("the XN-550 API types extend no clinical type and carry no internal field", () => {
  const types = read("types", "api.ts")
  for (const name of [
    "InstrumentResultSetSummary", "PaginatedInstrumentResultSetResponse", "InstrumentResultItemResponse",
    "InstrumentResultDeliveryResponse", "InstrumentResultProvenanceResponse", "InstrumentResultSetDetail",
  ]) {
    assert.match(types, new RegExp(`export interface ${name} \\{`), name)
  }
  const section = stripComments(types.slice(types.indexOf("export interface InstrumentResultSetSummary")))
  assert.ok(!/\bextends\b/.test(section))
  assert.ok(!/p5_populated|p8_populated|analysis_fingerprint|raw_bytes|raw_message|test_code_qualifier/.test(section))
})
