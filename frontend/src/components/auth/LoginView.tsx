import { useState, type FormEvent } from "react"
import { useAuth } from "./AuthProvider"
import { ApiError } from "../../api/client"

// Gate, not a route (design §12.2): App.tsx renders this in place of the
// worklist when there is no session, the same way it already switches
// between detail / search / overview views.
export function LoginView() {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (submitting) return

    setSubmitting(true)
    setError(null)

    login(username, password)
      .catch((err: unknown) => {
        const message =
          err instanceof ApiError && err.status === 401
            ? "Incorrect username or password."
            : "Unable to sign in. Please try again."
        setError(message)
      })
      .finally(() => setSubmitting(false))
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "var(--space-4)",
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-card)",
          maxWidth: 360,
          padding: "var(--space-8)",
          width: "100%",
        }}
      >
        <h1
          style={{
            fontSize: "1.125rem",
            fontWeight: 600,
            marginBottom: "var(--space-1)",
          }}
        >
          LIS Server
        </h1>
        <p
          style={{
            color: "var(--color-text-secondary)",
            fontSize: "0.8125rem",
            marginBottom: "var(--space-6)",
          }}
        >
          Sign in to continue.
        </p>

        <label
          htmlFor="login-username"
          style={{
            display: "block",
            fontSize: "0.75rem",
            fontWeight: 600,
            marginBottom: "var(--space-1)",
          }}
        >
          Username
        </label>
        <input
          autoComplete="username"
          autoFocus
          className="lis-input"
          disabled={submitting}
          id="login-username"
          name="username"
          onChange={(event) => setUsername(event.target.value)}
          required
          type="text"
          value={username}
          style={{
            border: "1px solid var(--color-border-input)",
            borderRadius: "var(--radius-md)",
            fontFamily: "var(--font-ui)",
            fontSize: "0.875rem",
            height: 36,
            marginBottom: "var(--space-4)",
            padding: "8px 12px",
            width: "100%",
          }}
        />

        <label
          htmlFor="login-password"
          style={{
            display: "block",
            fontSize: "0.75rem",
            fontWeight: 600,
            marginBottom: "var(--space-1)",
          }}
        >
          Password
        </label>
        <input
          autoComplete="current-password"
          className="lis-input"
          disabled={submitting}
          id="login-password"
          name="password"
          onChange={(event) => setPassword(event.target.value)}
          required
          type="password"
          value={password}
          style={{
            border: "1px solid var(--color-border-input)",
            borderRadius: "var(--radius-md)",
            fontFamily: "var(--font-ui)",
            fontSize: "0.875rem",
            height: 36,
            marginBottom: "var(--space-4)",
            padding: "8px 12px",
            width: "100%",
          }}
        />

        {error ? (
          <p
            role="alert"
            style={{
              color: "var(--color-flag-high)",
              fontSize: "0.8125rem",
              marginBottom: "var(--space-4)",
            }}
          >
            {error}
          </p>
        ) : null}

        <button
          className="lis-btn lis-btn--primary"
          disabled={submitting}
          style={{ width: "100%" }}
          type="submit"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  )
}
