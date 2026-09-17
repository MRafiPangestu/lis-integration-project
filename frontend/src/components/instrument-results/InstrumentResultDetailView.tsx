import type { CSSProperties } from "react";
import { ApiError } from "../../api/client";
import { useInstrumentResult } from "../../hooks/useInstrumentResult";
import type { InstrumentResultItemResponse, InstrumentResultSetDetail } from "../../types/api";
import { EmptyState } from "../status/EmptyState";
import { ErrorState } from "../status/ErrorState";
import { LoadingState } from "../status/LoadingState";
import { IdentityDisclaimer } from "./IdentityDisclaimer";
import { InstrumentFlag } from "./InstrumentFlag";
import {
  deliveryBadgeText,
  displayOrDash,
  duplicateBadgeText,
  formatNaiveDateTime,
  graphicsHeading,
  groupItemsByKind,
  imageReferenceCodes,
} from "./presentation";

export interface InstrumentResultDetailViewProps {
  idResultSet: number;
  onBack: () => void;
  onOpenResult: (idResultSet: number) => void;
}

const cardStyle: CSSProperties = {
  backgroundColor: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-lg)",
  boxShadow: "var(--shadow-card)",
  padding: "var(--space-4) var(--space-5)",
};

const headerCellStyle: CSSProperties = {
  borderBottom: "1px solid var(--color-border)",
  color: "var(--color-text-secondary)",
  fontSize: "0.75rem",
  fontWeight: 600,
  padding: "var(--space-2)",
  textAlign: "left",
  textTransform: "uppercase",
};

const cellStyle: CSSProperties = {
  borderBottom: "1px solid var(--color-border-subtle)",
  fontFamily: "var(--font-clinical)",
  padding: "var(--space-2)",
  textAlign: "left",
  verticalAlign: "top",
};

const labelStyle: CSSProperties = {
  color: "var(--color-text-secondary)",
  fontSize: "0.75rem",
  textTransform: "uppercase",
};

const pillStyle: CSSProperties = {
  background: "var(--color-neutral-bg)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-sm)",
  color: "var(--color-text-secondary)",
  fontSize: "0.75rem",
  fontWeight: 600,
  padding: "2px var(--space-2)",
};

// Contract C.3: one unlinked XN-550 result set. Read-only. No patient, visit or
// order field, no link to patient history or orders, no workflow control.
export function InstrumentResultDetailView({ idResultSet, onBack, onOpenResult }: InstrumentResultDetailViewProps) {
  const result = useInstrumentResult(idResultSet);
  const isNotFound = result.error instanceof ApiError && result.error.status === 404;

  let body;
  if (result.data === null && result.loading) {
    body = <LoadingState message="Loading the instrument result set…" />;
  } else if (result.data === null && isNotFound) {
    body = <EmptyState title="Result set not found" message="This unlinked instrument result set does not exist." />;
  } else if (result.data === null && result.error) {
    body = (
      <ErrorState
        error={result.error}
        message="Unable to load the instrument result set. Please try again."
        onRetry={result.refetch}
        title="Instrument result set unavailable"
      />
    );
  } else if (result.data) {
    body = <DetailBody detail={result.data} onOpenResult={onOpenResult} />;
  }

  return (
    <section aria-label={`Unlinked instrument result set #${idResultSet}`} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div>
        <button type="button" className="lis-btn lis-btn--secondary" onClick={onBack}>
          ← Back to unlinked instrument results
        </button>
      </div>
      {/* The identity disclaimer is shown in every state of the detail view. */}
      <IdentityDisclaimer notice={result.data?.identity_notice ?? null} />
      {body}
    </section>
  );
}

function DetailBody({
  detail,
  onOpenResult,
}: {
  detail: InstrumentResultSetDetail;
  onOpenResult: (idResultSet: number) => void;
}) {
  const duplicate = duplicateBadgeText(detail.possible_duplicate_of);
  const deliveries = deliveryBadgeText(detail.delivery_count);
  const groups = groupItemsByKind(detail.items);
  const graphics = imageReferenceCodes(detail.items);

  return (
    <>
      <div style={{ ...cardStyle, display: "grid", gap: "var(--space-3)", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
        <HeaderField label="Received (LIS time)" value={formatNaiveDateTime(detail.received_at)} />
        <HeaderField label="Analysed (instrument clock)" value={formatNaiveDateTime(detail.analysis_at)} />
        <HeaderField label="Sample No. (as entered on instrument)" value={detail.sample_label} />
        <HeaderField label="Instrument" value={detail.instrument_name} />
        <div style={{ gridColumn: "1 / -1", display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
          {duplicate !== null && detail.possible_duplicate_of !== null ? (
            <button
              type="button"
              onClick={() => onOpenResult(detail.possible_duplicate_of as number)}
              style={{ ...pillStyle, cursor: "pointer", font: "inherit", fontSize: "0.75rem" }}
            >
              {duplicate}
            </button>
          ) : null}
          {deliveries !== null ? <span style={pillStyle}>{deliveries}</span> : null}
        </div>
      </div>

      {groups.map((group) => (
        <section key={group.kind} aria-label={group.title} style={cardStyle}>
          <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: "var(--space-2)" }}>{group.title}</h3>
          {group.caption !== null ? (
            <p style={{ color: "var(--color-text-secondary)", fontSize: "0.8125rem", marginBottom: "var(--space-2)" }}>
              {group.caption}
            </p>
          ) : null}
          <ObservationTable items={group.items} />
        </section>
      ))}

      {graphics.length > 0 ? (
        <section aria-label="Graphics referenced on the instrument" style={cardStyle}>
          <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, marginBottom: "var(--space-2)" }}>
            {graphicsHeading(graphics.length)}
          </h3>
          <ul style={{ margin: 0, paddingLeft: "var(--space-5)", fontFamily: "var(--font-clinical)", fontSize: "0.8125rem" }}>
            {graphics.map((code) => (
              <li key={code}>{code}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <details style={cardStyle}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Provenance</summary>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
          <table style={{ borderCollapse: "collapse", fontSize: "0.8125rem", width: "100%" }}>
            <caption style={{ textAlign: "left", color: "var(--color-text-secondary)", paddingBottom: "var(--space-1)" }}>
              Deliveries of these exact bytes
            </caption>
            <thead>
              <tr>
                <th scope="col" style={headerCellStyle}>Message</th>
                <th scope="col" style={headerCellStyle}>Received (LIS time)</th>
                <th scope="col" style={headerCellStyle}>Session</th>
                <th scope="col" style={headerCellStyle}>Reads</th>
              </tr>
            </thead>
            <tbody>
              {detail.deliveries.map((delivery) => (
                <tr key={delivery.id_message}>
                  <td style={cellStyle}>#{delivery.id_message}</td>
                  <td style={cellStyle}>{formatNaiveDateTime(delivery.received_at)}</td>
                  <td style={cellStyle}>#{delivery.id_session}</td>
                  <td style={cellStyle}>{delivery.read_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "var(--space-1) var(--space-4)", fontSize: "0.8125rem", margin: 0 }}>
            <dt style={labelStyle}>Parser</dt>
            <dd style={{ margin: 0, fontFamily: "var(--font-clinical)" }}>
              {detail.provenance.parser_key} {detail.provenance.parser_version}
            </dd>
            <dt style={labelStyle}>SHA-256 prefix</dt>
            <dd style={{ margin: 0, fontFamily: "var(--font-clinical)" }}>{detail.provenance.raw_sha256_prefix}</dd>
            <dt style={labelStyle}>Raw length</dt>
            <dd style={{ margin: 0, fontFamily: "var(--font-clinical)" }}>{detail.provenance.raw_length} bytes</dd>
            <dt style={labelStyle}>ACK policy</dt>
            <dd style={{ margin: 0, fontFamily: "var(--font-clinical)" }}>{detail.provenance.ack_policy}</dd>
          </dl>
        </div>
      </details>
    </>
  );
}

function HeaderField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={labelStyle}>{label}</div>
      <div style={{ fontFamily: "var(--font-clinical)", fontSize: "0.9375rem", marginTop: 2 }}>{value}</div>
    </div>
  );
}

// XN-550-specific observation table. Never the clinical ResultTable / ResultRow.
function ObservationTable({ items }: { items: InstrumentResultItemResponse[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: "0.875rem", minWidth: 640, width: "100%" }}>
        <thead>
          <tr>
            <th scope="col" style={headerCellStyle}>Parameter</th>
            <th scope="col" style={headerCellStyle}>Value</th>
            <th scope="col" style={headerCellStyle}>Units</th>
            <th scope="col" style={headerCellStyle}>Reference range</th>
            <th scope="col" style={headerCellStyle}>Instrument flag</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.test_code}>
              <td style={cellStyle}>{item.test_code}</td>
              <td style={cellStyle}>{displayOrDash(item.value)}</td>
              <td style={cellStyle}>{displayOrDash(item.units)}</td>
              <td style={cellStyle}>—</td>
              <td style={{ ...cellStyle, fontFamily: "inherit" }}>
                <InstrumentFlag flag={item.abnormal_flag} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
