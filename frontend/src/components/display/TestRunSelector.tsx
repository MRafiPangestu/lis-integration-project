import type { TestRunResponse } from "../../types/api"

export interface TestRunSelectorProps {
  testRuns: TestRunResponse[]
  selectedRunId: number | null
  onSelect: (runId: number) => void
  disabled?: boolean
}

function formatDateTime(value: string | null): string {
  if (!value) return "—"

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed)
}

export function TestRunSelector({
  testRuns,
  selectedRunId,
  onSelect,
  disabled = false,
}: TestRunSelectorProps) {
  return (
    <section aria-labelledby="test-run-selector-title">
      <h2
        id="test-run-selector-title"
        style={{ fontSize: "1rem", marginBottom: "var(--space-2)" }}
      >
        Test Runs
      </h2>
      {testRuns.length === 0 ? (
        <p style={{ color: "var(--color-text-secondary)" }}>
          No Test Run available for this Order.
        </p>
      ) : (
        <div
          role="tablist"
          aria-label="Test runs"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-2)",
          }}
        >
          {testRuns.map((run) => {
            const isSelected = run.id_run === selectedRunId
            const runLabel = `Run ${run.run_sequence}`

            return (
              <button
                key={run.id_run}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-label={`${runLabel}${run.is_final ? ", final" : ""}`}
                disabled={disabled}
                onClick={() => onSelect(run.id_run)}
                style={{
                  alignItems: "flex-start",
                  backgroundColor: isSelected
                    ? "var(--color-surface-hover)"
                    : "var(--color-surface)",
                  border: isSelected
                    ? "2px solid var(--color-primary)"
                    : "1px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--color-text-primary)",
                  cursor: disabled ? "not-allowed" : "pointer",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-1)",
                  minWidth: "140px",
                  padding: "var(--space-2) var(--space-3)",
                  textAlign: "left",
                }}
              >
                <span style={{ fontWeight: 600 }}>{runLabel}</span>
                <span
                  style={{
                    color: "var(--color-text-secondary)",
                    fontFamily: "var(--font-clinical)",
                    fontSize: "0.75rem",
                  }}
                >
                  {formatDateTime(run.waktu_run)}
                </span>
                {isSelected ? (
                  <span style={{ color: "var(--color-primary)", fontSize: "0.75rem" }}>
                    Active
                  </span>
                ) : null}
                {run.is_final ? (
                  <span style={{ fontSize: "0.75rem", fontWeight: 600 }}>
                    ★ FINAL
                  </span>
                ) : null}
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
