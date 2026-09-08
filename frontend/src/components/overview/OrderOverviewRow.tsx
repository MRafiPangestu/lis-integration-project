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
  borderBottom: "1px solid var(--color-border)",
  padding: "var(--space-2) var(--space-3)",
  verticalAlign: "middle",
};

const badgeStyle: CSSProperties = {
  border: "1px solid var(--color-border)",
  borderRadius: "999px",
  fontSize: "0.72rem",
  padding: "1px var(--space-2)",
  whiteSpace: "nowrap",
};

export function OrderOverviewRow({ row, onOpen }: OrderOverviewRowProps) {
  const [focused, setFocused] = useState(false);
  const activate = () => onOpen(row);

  const showRun = row.effective_run_sequence !== null && row.effective_run_sequence > 1;

  return (
    <tr
      onClick={activate}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      style={{
        cursor: "pointer",
        backgroundColor: focused ? "var(--color-surface-hover)" : undefined,
      }}
    >
      <td style={{ ...cellStyle, width: "40%" }}>
        <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>{row.nama_lengkap}</div>
        <div
          style={{
            color: "var(--color-text-secondary)",
            fontFamily: "var(--font-clinical)",
            fontSize: "0.75rem",
          }}
        >
          {row.nomor_rm} · {row.no_registrasi}
        </div>
      </td>

      <td
        style={{
          ...cellStyle,
          fontFamily: "var(--font-clinical)",
          fontSize: "0.85rem",
          whiteSpace: "nowrap",
        }}
      >
        {formatOrderTime(row.waktu_order)}
      </td>

      <td style={cellStyle}>
        <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: "var(--space-1)" }}>
          <span style={{ fontSize: "0.85rem" }}>{row.status_order}</span>
          {row.is_final ? (
            <span
              style={{
                ...badgeStyle,
                borderColor: "var(--color-flag-normal)",
                color: "var(--color-flag-normal)",
              }}
            >
              Final
            </span>
          ) : (
            <span style={{ ...badgeStyle, color: "var(--color-text-secondary)" }}>
              Not finalised
            </span>
          )}
          {row.delivery_status !== null ? (
            <span style={{ ...badgeStyle, color: "var(--color-text-secondary)" }}>
              {row.delivery_status}
            </span>
          ) : null}
          {showRun ? (
            <span style={{ ...badgeStyle, color: "var(--color-text-secondary)" }}>
              Run {row.effective_run_sequence}
            </span>
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
              color: "var(--color-flag-high)",
              display: "inline-flex",
              fontWeight: 600,
              gap: "var(--space-1)",
            }}
          >
            <span aria-hidden="true">⚠</span>
            <span>
              {row.abnormal_count} abnormal
            </span>
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
            background: "none",
            border: "1px solid transparent",
            borderRadius: "4px",
            color: "var(--color-text-secondary)",
            cursor: "pointer",
            fontSize: "1rem",
            lineHeight: 1,
            padding: "var(--space-1) var(--space-2)",
          }}
        >
          <span aria-hidden="true">›</span>
        </button>
      </td>
    </tr>
  );
}
