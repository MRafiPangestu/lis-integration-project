import { useEffect, useRef } from "react"

export interface ConfirmationDialogProps {
  open: boolean
  title: string
  message: string
  onConfirm: () => void | Promise<void>
  onCancel: () => void
  confirmLabel?: string
  cancelLabel?: string
  loading?: boolean
}

export function ConfirmationDialog({
  open,
  title,
  message,
  onConfirm,
  onCancel,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  loading = false,
}: ConfirmationDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef(onCancel)
  const loadingRef = useRef(loading)

  cancelRef.current = onCancel
  loadingRef.current = loading

  useEffect(() => {
    if (!open) return

    const previousFocus = document.activeElement as HTMLElement | null
    const focusableSelector =
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    const getFocusableElements = () =>
      Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? [])

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (!loadingRef.current) cancelRef.current()
        return
      }

      if (event.key !== "Tab") return

      const focusableElements = getFocusableElements()
      if (focusableElements.length === 0) {
        event.preventDefault()
        dialogRef.current?.focus()
        return
      }

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]
      const activeElement = document.activeElement

      if (!dialogRef.current?.contains(activeElement)) {
        event.preventDefault()
        ;(event.shiftKey ? lastElement : firstElement).focus()
        return
      }

      if (event.shiftKey && activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (!event.shiftKey && activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }

    const firstFocusableElement = getFocusableElements()[0]
    ;(firstFocusableElement ?? dialogRef.current)?.focus()

    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

  if (!open) return null

  return (
    <div
      role="presentation"
      style={{
        alignItems: "center",
        backgroundColor: "rgba(17, 24, 39, 0.45)",
        display: "flex",
        inset: 0,
        justifyContent: "center",
        padding: "var(--space-4)",
        position: "fixed",
        zIndex: 90,
      }}
    >
      <div
        aria-describedby="confirmation-dialog-message"
        aria-labelledby="confirmation-dialog-title"
        aria-modal="true"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          maxWidth: "480px",
          padding: "var(--space-6)",
          width: "100%",
        }}
      >
        <h2 id="confirmation-dialog-title" style={{ fontSize: "1.125rem", marginBottom: "var(--space-2)" }}>
          {title}
        </h2>
        <p id="confirmation-dialog-message" style={{ color: "var(--color-text-secondary)" }}>
          {message}
        </p>
        <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end", marginTop: "var(--space-6)" }}>
          <button className="lis-btn lis-btn--secondary" disabled={loading} onClick={onCancel} type="button">
            {cancelLabel}
          </button>
          <button className="lis-btn lis-btn--primary" disabled={loading} onClick={() => void onConfirm()} type="button">
            {loading ? "Working..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
