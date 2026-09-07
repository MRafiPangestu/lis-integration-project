export interface EmptyStateProps {
  title?: string
  message?: string
}

export function EmptyState({
  title = "No data available",
  message = "There are no records to display.",
}: EmptyStateProps) {
  return (
    <section
      aria-live="polite"
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "4px",
        padding: "var(--space-6)",
        textAlign: "center",
      }}
    >
      <h2 style={{ fontSize: "1rem", marginBottom: "var(--space-2)" }}>
        {title}
      </h2>
      <p style={{ color: "var(--color-text-secondary)" }}>{message}</p>
    </section>
  )
}
