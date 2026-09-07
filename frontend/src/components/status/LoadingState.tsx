export interface LoadingStateProps {
  message?: string
}

export function LoadingState({ message = "Loading..." }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      style={{
        alignItems: "center",
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "4px",
        color: "var(--color-text-secondary)",
        display: "flex",
        gap: "var(--space-2)",
        padding: "var(--space-4)",
      }}
    >
      <span aria-hidden="true" style={{ fontSize: "1.25rem" }}>
        ◌
      </span>
      <span>{message}</span>
    </div>
  )
}
