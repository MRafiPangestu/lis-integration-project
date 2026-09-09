import { useState } from "react";
import type { CSSProperties } from "react";
import type { OrderOverviewRow as OrderOverviewRowData } from "../../types/api";

export interface OrderOverviewRowProps {
  row: OrderOverviewRowData;
  onOpen: (row: OrderOverviewRowData) => void;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

// Display only (dd/MM HH:mm). waktu_order is server-local naive; parsing it as a
// local Date for display is correct and unrelated to the transport rule.
function formatOrderTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return (
    `${pad(parsed.getDate())}/${pad(parsed.getMonth() + 1)} ` +
    `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  );
}

const cellStyle: CSSProperties = {
  borderBottom: "1px solid var(--color-border-subtle)",
  padding: "14px var(--space-5)",
  verticalAlign: "middle",
};

const pillStyle: CSSProperties = {
  borderRadius: "var(--radius-sm)",
  fontSize: "0.6875rem",
  fontWeight: 600,
  padding: "2px var(--space-2)",
  whiteSpace: "nowrap",
};

const neutralPillStyle: CSSProperties = {
  ...pillStyle,
  background: "var(--color-neutral-bg)",
  color: "var(--color-text-secondary)",
};

export function OrderOverviewRow({ row, onOpen }: OrderOverviewRowProps) {
  const [highlighted, setHighlighted] = useState(false);
  const activate = () => onOpen(row);

  const showRun = row.effective_run_sequence !== null && row.effective_run_sequence > 1;

  return (
    <tr
      onClick={activate}
      onMouseEnter={() => setHighlighted(true)}
      onMouseLeave={() => setHighlighted(false)}
      onFocus={() => setHighlighted(true)}
      onBlur={() => setHighlighted(false)}
      style={{
        cursor: "pointer",
        backgroundColor: highlighted ? "var(--color-surface-hover)" : undefined,
      }}
    >
      <td style={cellStyle}>
        <div
          style={{
            fontSize: "0.875rem",
            fontWeight: 600,
            color: "var(--color-text-primary)",
          }}
        >
          {row.nama_lengkap}
        </div>
        <div
          style={{
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-clinical)",
            fontSize: "0.75rem",
            marginTop: 2,
          }}
        >
          {row.nomor_rm} · {row.no_registrasi}
        </div>
      </td>

      <td
        style={{
          ...cellStyle,
          fontFamily: "var(--font-clinical)",
          fontSize: "0.8125rem",
          color: "var(--color-text-secondary)",
          whiteSpace: "nowrap",
        }}
      >
        {formatOrderTime(row.waktu_order)}
      </td>

      <td style={cellStyle}>
        <div
          style={{
            alignItems: "center",
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-1)",
          }}
        >
          <span style={{ fontSize: "0.8125rem", color: "var(--color-text-primary)" }}>
            {row.status_order}
          </span>
          {row.is_final ? (
            <span
              style={{
                ...pillStyle,
                background: "var(--color-success-bg)",
                color: "var(--color-success-text)",
              }}
            >
              Final
            </span>
          ) : (
            <span style={neutralPillStyle}>Not finalised</span>
          )}
          {row.delivery_status !== null ? (
            <span style={neutralPillStyle}>{row.delivery_status}</span>
          ) : null}
          {showRun ? (
            <span style={neutralPillStyle}>Run {row.effective_run_sequence}</span>
          ) : null}
        </div>
      </td>

      <td style={{ ...cellStyle, whiteSpace: "nowrap" }}>
        {row.abnormal_count === 0 ? (
          <span style={{ color: "var(--color-text-disabled)" }}>—</span>
        ) : (
          <span
            style={{
              alignItems: "center",
              background: "var(--color-danger-bg)",
              color: "var(--color-danger-text)",
              borderRadius: "var(--radius-sm)",
              display: "inline-flex",
              fontSize: "0.75rem",
              fontWeight: 700,
              gap: "var(--space-1)",
              padding: "2px var(--space-2)",
            }}
          >
            <span aria-hidden="true">⚠</span>
            <span>{row.abnormal_count} abnormal</span>
          </span>
        )}
      </td>

      <td style={{ ...cellStyle, textAlign: "right", width: 44 }}>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            activate();
          }}
          aria-label={`Open worklist detail for ${row.nama_lengkap}, order ${row.id_order}`}
          style={{
            alignItems: "center",
            background: "none",
            border: "none",
            borderRadius: "var(--radius-sm)",
            color: "var(--color-text-disabled)",
            cursor: "pointer",
            display: "inline-flex",
            height: 28,
            justifyContent: "center",
            lineHeight: 1,
            width: 28,
          }}
        >
          <span aria-hidden="true" style={{ fontSize: "1rem" }}>
            ›
          </span>
        </button>
      </td>
    </tr>
  );
}
