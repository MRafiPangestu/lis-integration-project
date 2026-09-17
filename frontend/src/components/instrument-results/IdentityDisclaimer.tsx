import { IDENTITY_DISCLAIMER_TEXT, IDENTITY_NOTICE_CODE } from "./presentation";

export interface IdentityDisclaimerProps {
  // The API's machine-readable identity_notice. The disclaimer is shown
  // whatever its value — it can never be hidden or dismissed.
  notice?: string | null;
}

// Contract C.2 / C.3: persistent, non-dismissible identity disclaimer shown on
// both the list and the detail view of unlinked instrument results.
export function IdentityDisclaimer({ notice }: IdentityDisclaimerProps) {
  return (
    <div
      role="note"
      aria-label="Identity notice"
      data-identity-notice={notice ?? IDENTITY_NOTICE_CODE}
      style={{
        backgroundColor: "var(--color-neutral-bg)",
        border: "1px solid var(--color-border-strong)",
        borderLeft: "4px solid var(--color-flag-low)",
        borderRadius: "var(--radius-md)",
        color: "var(--color-text-primary)",
        fontSize: "0.8125rem",
        lineHeight: 1.5,
        padding: "var(--space-3) var(--space-4)",
      }}
    >
      <strong style={{ display: "block", marginBottom: "var(--space-1)" }}>
        Unlinked instrument results — identity unresolved
      </strong>
      {IDENTITY_DISCLAIMER_TEXT}
    </div>
  );
}
