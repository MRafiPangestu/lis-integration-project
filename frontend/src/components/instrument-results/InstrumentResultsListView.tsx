import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { INSTRUMENT_RESULTS_PAGE_SIZE, useInstrumentResults } from "../../hooks/useInstrumentResults";
import type { InstrumentResultSetSummary } from "../../types/api";
import { DateRangeFilter } from "../overview/DateRangeFilter";
import { Pagination } from "../overview/Pagination";
import { ALL_DATE_FROM, ALL_DATE_TO } from "../overview/dateRange";
import { EmptyState } from "../status/EmptyState";
import { ErrorState } from "../status/ErrorState";
import { LoadingState } from "../status/LoadingState";
import { IdentityDisclaimer } from "./IdentityDisclaimer";
import {
  UNLINKED_ALL_DATES_CAPTION,
  deliveryBadgeText,
  duplicateBadgeText,
  formatNaiveDateTime,
} from "./presentation";

export interface InstrumentResultsListViewProps {
  instrumentId: number;
  instrumentName: string;
  receivedFrom: string;
  receivedTo: string;
  page: number;
  onRangeChange: (receivedFrom: string, receivedTo: string) => void;
  onPageChange: (page: number) => void;
  onOpenResult: (idResultSet: number) => void;
}

const headerCellStyle: CSSProperties = {
  backgroundColor: "var(--color-background)",
  borderBottom: "1px solid var(--color-border)",
  color: "var(--color-text-secondary)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "0.02em",
  padding: "var(--space-3) var(--space-4)",
  textAlign: "left",
  textTransform: "uppercase",
};

const cellStyle: CSSProperties = {
  borderBottom: "1px solid var(--color-border-subtle)",
  padding: "12px var(--space-4)",
  verticalAlign: "middle",
};

const clinicalTextStyle: CSSProperties = {
  fontFamily: "var(--font-clinical)",
  fontSize: "0.8125rem",
};

const pillStyle: CSSProperties = {
  background: "var(--color-neutral-bg)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-sm)",
  color: "var(--color-text-secondary)",
  display: "inline-block",
  fontSize: "0.6875rem",
  fontWeight: 600,
  margin: "2px var(--space-1) 2px 0",
  padding: "2px var(--space-2)",
  whiteSpace: "nowrap",
};

// Contract C.2: the list of unlinked XN-550 result sets for one instrument.
// Not a patient worklist: no patient, visit or order field, no search, and the
// identity disclaimer is always shown.
export function InstrumentResultsListView({
  instrumentId,
  instrumentName,
  receivedFrom,
  receivedTo,
  page,
  onRangeChange,
  onPageChange,
  onOpenResult,
}: InstrumentResultsListViewProps) {
  const results = useInstrumentResults(instrumentId, receivedFrom, receivedTo, page);
  const isAllRange = receivedFrom === ALL_DATE_FROM && receivedTo === ALL_DATE_TO;

  let body;
  if (results.data === null && results.loading) {
    body = <LoadingState message="Loading unlinked instrument results…" />;
  } else if (results.data === null && results.error) {
    body = (
      <ErrorState
        error={results.error}
        message="Unable to load unlinked instrument results. Please try again."
        onRetry={results.refetch}
        title="Unlinked instrument results unavailable"
      />
    );
  } else if (results.data && results.data.total === 0) {
    body = (
      <EmptyState
        title="No unlinked instrument results"
        message={
          isAllRange
            ? "No unlinked results were received from this instrument."
            : `No unlinked results were received from this instrument between ${receivedFrom} and ${receivedTo}.`
        }
      />
    );
  } else if (results.data) {
    body = (
      <ResultSetTable
        rows={results.data.items}
        refreshing={results.loading}
        onOpenResult={onOpenResult}
        footer={
          <Pagination
            page={results.data.page}
            pageSize={INSTRUMENT_RESULTS_PAGE_SIZE}
            total={results.data.total}
            loading={results.loading}
            onPageChange={onPageChange}
          />
        }
      />
    );
  }

  return (
    <section
      aria-label={`Unlinked instrument results for ${instrumentName}`}
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "var(--space-2)" }}>
        <h2 style={{ fontSize: "1rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
          Unlinked instrument results
        </h2>
        {results.data ? (
          <span style={{ color: "var(--color-text-secondary)", fontSize: "0.8125rem" }}>
            · {results.data.total} result {results.data.total === 1 ? "set" : "sets"}
          </span>
        ) : null}
      </div>
      <IdentityDisclaimer notice={results.data?.identity_notice ?? null} />
      <DateRangeFilter
        dateFrom={receivedFrom}
        dateTo={receivedTo}
        onChange={onRangeChange}
        allCaption={UNLINKED_ALL_DATES_CAPTION}
      />
      {body}
    </section>
  );
}

interface ResultSetTableProps {
  rows: InstrumentResultSetSummary[];
  refreshing: boolean;
  onOpenResult: (idResultSet: number) => void;
  footer: ReactNode;
}

function ResultSetTable({ rows, refreshing, onOpenResult, footer }: ResultSetTableProps) {
  return (
    <div
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-card)",
        overflow: "hidden",
        opacity: refreshing ? 0.6 : 1,
      }}
    >
      <div className="custom-scrollbar" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", minWidth: 960, borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr>
              <th scope="col" style={headerCellStyle}>Received (LIS time)</th>
              <th scope="col" style={headerCellStyle}>Analysed (instrument clock)</th>
              <th scope="col" style={headerCellStyle}>Sample No. (as entered on instrument)</th>
              <th scope="col" style={headerCellStyle}>Instrument</th>
              <th scope="col" style={headerCellStyle}>Items with instrument flag other than N</th>
              <th scope="col" style={headerCellStyle}>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <ResultSetRow key={row.id_result_set} row={row} onOpenResult={onOpenResult} />
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ borderTop: "1px solid var(--color-border)" }}>{footer}</div>
    </div>
  );
}

function ResultSetRow({
  row,
  onOpenResult,
}: {
  row: InstrumentResultSetSummary;
  onOpenResult: (idResultSet: number) => void;
}) {
  const [highlighted, setHighlighted] = useState(false);
  const duplicate = duplicateBadgeText(row.possible_duplicate_of);
  const deliveries = deliveryBadgeText(row.delivery_count);

  return (
    <tr
      tabIndex={0}
      onClick={() => onOpenResult(row.id_result_set)}
      onKeyDown={(event) => {
        if (event.key === "Enter") onOpenResult(row.id_result_set);
      }}
      onMouseEnter={() => setHighlighted(true)}
      onMouseLeave={() => setHighlighted(false)}
      aria-label={`Open unlinked result set #${row.id_result_set}`}
      style={{ cursor: "pointer", backgroundColor: highlighted ? "var(--color-surface-hover)" : undefined }}
    >
      <td style={{ ...cellStyle, ...clinicalTextStyle }}>{formatNaiveDateTime(row.received_at)}</td>
      <td style={{ ...cellStyle, ...clinicalTextStyle }}>{formatNaiveDateTime(row.analysis_at)}</td>
      <td style={{ ...cellStyle, ...clinicalTextStyle }}>{row.sample_label}</td>
      <td style={cellStyle}>{row.instrument_name}</td>
      <td style={{ ...cellStyle, ...clinicalTextStyle }}>{row.non_n_flag_item_count}</td>
      <td style={cellStyle}>
        {duplicate !== null && row.possible_duplicate_of !== null ? (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onOpenResult(row.possible_duplicate_of as number);
            }}
            style={{ ...pillStyle, cursor: "pointer", font: "inherit", fontSize: "0.6875rem" }}
          >
            {duplicate}
          </button>
        ) : null}
        {deliveries !== null ? <span style={pillStyle}>{deliveries}</span> : null}
        {duplicate === null && deliveries === null ? (
          <span style={{ color: "var(--color-text-secondary)" }}>—</span>
        ) : null}
      </td>
    </tr>
  );
}
