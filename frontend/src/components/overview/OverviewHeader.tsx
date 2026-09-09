export interface OverviewHeaderProps {
  total: number | null;
  loading: boolean;
}

// Row 1 (left) of the overview toolbar: section title + order count. The active
// instrument name lives in the top Header now (D2 de-duplication).
export function OverviewHeader({ total, loading }: OverviewHeaderProps) {
  const count =
    total === null ? (loading ? "Loading…" : "") : `${total} order${total === 1 ? "" : "s"}`;

  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)", minWidth: 0 }}>
      <span style={{ fontSize: "1rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
        Order worklist
      </span>
      {count ? (
        <span style={{ color: "var(--color-text-secondary)", fontSize: "0.8125rem" }}>
          · {count}
        </span>
      ) : null}
    </div>
  );
}
