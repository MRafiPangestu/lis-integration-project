import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react"

type ToastKind = "success" | "error"

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

interface ToastContextValue {
  showSuccess: (message: string) => void
  showError: (message: string) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const show = useCallback((kind: ToastKind, message: string) => {
    const trimmedMessage = message.trim()
    if (!trimmedMessage) return

    const id = nextId.current++
    setToasts((current) => [...current, { id, kind, message: trimmedMessage }])
  }, [])

  const showSuccess = useCallback((message: string) => show("success", message), [show])
  const showError = useCallback((message: string) => show("error", message), [show])
  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ dismiss, showError, showSuccess }}>
      {children}
      <div
        aria-label="Notifications"
        style={{
          bottom: "var(--space-4)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-2)",
          maxWidth: "min(420px, calc(100vw - 32px))",
          position: "fixed",
          right: "var(--space-4)",
          width: "100%",
          zIndex: 100,
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.kind === "error" ? "alert" : "status"}
            aria-live={toast.kind === "error" ? "assertive" : "polite"}
            style={{
              alignItems: "flex-start",
              backgroundColor: "var(--color-surface)",
              border: `1px solid ${toast.kind === "error" ? "var(--color-flag-high)" : "var(--color-flag-normal)"}`,
              borderRadius: "4px",
              boxShadow: "0 4px 12px rgba(17, 24, 39, 0.15)",
              display: "flex",
              gap: "var(--space-3)",
              justifyContent: "space-between",
              padding: "var(--space-3)",
            }}
          >
            <span>{toast.message}</span>
            <button
              aria-label="Dismiss notification"
              onClick={() => dismiss(toast.id)}
              type="button"
              style={{
                background: "none",
                border: 0,
                color: "var(--color-text-secondary)",
                cursor: "pointer",
                fontSize: "1rem",
                lineHeight: 1,
                padding: "var(--space-1)",
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error("useToast must be used within ToastProvider")
  }

  return context
}
