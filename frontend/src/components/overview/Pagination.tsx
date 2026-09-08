export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}

const buttonStyle = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "4px",
  color: "var(--color-text-primary)",
  cursor: "pointer",
  padding: "var(--space-1) var(--space-3)",
} as const;

export function Pagination({ page, pageSize, total, loading, onPageChange }: PaginationProps) {
  const firstRow = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);
  const previousDisabled = loading || page <= 1;
  const nextDisabled = loading || page * pageSize >= total;

  return (
    <div
      style={{
        alignItems: "center",
        display: "flex",
        gap: "var(--space-3)",
        justifyContent: "space-between",
        padding: "var(--space-2) 0",
      }}
    >
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={previousDisabled}
        style={{ ...buttonStyle, opacity: previousDisabled ? 0.5 : 1 }}
      >
        ‹ Previous
      </button>

      <span
        aria-live="polite"
        style={{ color: "var(--color-text-secondary)", fontSize: "0.85rem" }}
      >
        Showing {firstRow}–{lastRow} of {total}
      </span>

      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={nextDisabled}
        style={{ ...buttonStyle, opacity: nextDisabled ? 0.5 : 1 }}
      >
        Next ›
      </button>
    </div>
  );
}
