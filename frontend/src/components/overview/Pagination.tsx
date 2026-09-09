import type { CSSProperties } from "react";

export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}

const chevron = (direction: "left" | "right") => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d={direction === "left" ? "m15 18-6-6 6-6" : "m9 18 6-6-6-6"} />
  </svg>
);

const footerStyle: CSSProperties = {
  alignItems: "center",
  display: "flex",
  flexWrap: "wrap",
  gap: "var(--space-3)",
  justifyContent: "space-between",
  padding: "var(--space-4) var(--space-5)",
};

// Centred sliding window of five pages, first and last always rendered, with
// inert ellipses for the gaps. Every entry drives the existing server-side
// `page` parameter via onPageChange — no client-side dataset, no local derivation.
function pageWindow(page: number, totalPages: number): (number | "ellipsis")[] {
  if (totalPages <= 1) return [];

  const windowSize = 5;
  let start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + windowSize - 1);
  start = Math.max(1, end - windowSize + 1);

  const items: (number | "ellipsis")[] = [1];
  if (start > 2) items.push("ellipsis");
  for (let n = start; n <= end; n += 1) {
    if (n !== 1 && n !== totalPages) items.push(n);
  }
  if (end < totalPages - 1) items.push("ellipsis");
  items.push(totalPages);
  return items;
}

export function Pagination({ page, pageSize, total, loading, onPageChange }: PaginationProps) {
  const firstRow = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const previousDisabled = loading || page <= 1;
  const nextDisabled = loading || page * pageSize >= total;

  return (
    <div style={footerStyle}>
      <span
        aria-live="polite"
        style={{ color: "var(--color-text-secondary)", fontSize: "0.8125rem" }}
      >
        Showing <strong>{firstRow}–{lastRow}</strong> of <strong>{total}</strong>
      </span>

      <nav
        aria-label="Worklist pagination"
        style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "var(--space-1)" }}
      >
        <button
          type="button"
          className="lis-page-btn"
          onClick={() => onPageChange(page - 1)}
          disabled={previousDisabled}
          aria-label="Previous page"
          title="Previous page"
        >
          {chevron("left")}
        </button>

        {pageWindow(page, totalPages).map((entry, index) =>
          entry === "ellipsis" ? (
            <span
              key={`ellipsis-${index}`}
              aria-hidden="true"
              style={{ color: "var(--color-text-disabled)", padding: "0 var(--space-1)" }}
            >
              …
            </span>
          ) : (
            <button
              key={entry}
              type="button"
              className={
                entry === page
                  ? "lis-page-btn lis-page-num is-active"
                  : "lis-page-btn lis-page-num"
              }
              onClick={() => onPageChange(entry)}
              aria-label={`Page ${entry}`}
              aria-current={entry === page ? "page" : undefined}
            >
              {entry}
            </button>
          ),
        )}

        <button
          type="button"
          className="lis-page-btn"
          onClick={() => onPageChange(page + 1)}
          disabled={nextDisabled}
          aria-label="Next page"
          title="Next page"
        >
          {chevron("right")}
        </button>
      </nav>
    </div>
  );
}
