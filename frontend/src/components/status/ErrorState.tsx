export interface ErrorStateProps {
  error: Error
  title?: string
  message?: string
  onRetry?: () => void | Promise<void>
}

export function ErrorState({
  error,
  title = "Unable to load data",
  message,
  onRetry,
}: ErrorStateProps) {
  const hasErrorMessage = error.message.trim().length > 0
  const displayMessage =
    message ??
    (hasErrorMessage
      ? "Please try again or contact support if the problem persists."
      : "An unexpected error occurred. Please try again.")

  return (
    <section
      role="alert"
      aria-live="assertive"
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-6)",
      }}
    >
      <h2 style={{ fontSize: "1rem", marginBottom: "var(--space-2)" }}>
        {title}
      </h2>
      <p style={{ color: "var(--color-text-secondary)" }}>{displayMessage}</p>
      {onRetry ? (
        <button
          className="lis-btn lis-btn--primary"
          type="button"
          onClick={() => {
            void onRetry()
          }}
          style={{
            border: "1px solid var(--color-primary)",
            color: "var(--color-surface)",
            cursor: "pointer",
            marginTop: "var(--space-4)",
          }}
        >
          Retry
        </button>
      ) : null}
    </section>
  )
}
