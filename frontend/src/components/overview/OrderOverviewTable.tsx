import type { CSSProperties, ReactNode } from "react";
import type { OrderOverviewRow as OrderOverviewRowData } from "../../types/api";
import { OrderOverviewRow } from "./OrderOverviewRow";

export interface OrderOverviewTableProps {
  rows: OrderOverviewRowData[];
  onOpenOrder: (row: OrderOverviewRowData) => void;
  emptyMessage?: string;
  refreshing?: boolean;
  footer?: ReactNode;
}

const headerCellStyle: CSSProperties = {
  backgroundColor: "var(--color-background)",
  borderBottom: "1px solid var(--color-border)",
  color: "var(--color-text-secondary)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "0.02em",
  padding: "var(--space-4) var(--space-5)",
  textAlign: "left",
  textTransform: "uppercase",
};

const srOnly: CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
};

export function OrderOverviewTable({
  rows,
  onOpenOrder,
  emptyMessage,
  refreshing = false,
  footer,
}: OrderOverviewTableProps) {
  return (
    <div
      style={{
        position: "relative",
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-card)",
        overflow: "hidden",
      }}
    >
      {refreshing ? (
        <p
          role="status"
          style={{
            position: "absolute",
            top: "var(--space-2)",
            right: "var(--space-4)",
            zIndex: 1,
            fontSize: "0.75rem",
            color: "var(--color-text-secondary)",
          }}
        >
          Refreshing…
        </p>
      ) : null}

      <div
        className="custom-scrollbar"
        style={{
          overflowX: "auto",
          minHeight: 300,
          opacity: refreshing ? 0.6 : 1,
        }}
      >
        <table
          style={{
            width: "100%",
            minWidth: 900,
            borderCollapse: "collapse",
            fontSize: "0.875rem",
            textAlign: "left",
          }}
        >
          <thead>
            <tr>
              <th scope="col" style={{ ...headerCellStyle, width: "40%" }}>
                Patient
              </th>
              <th scope="col" style={{ ...headerCellStyle, width: "15%" }}>
                Order time
              </th>
              <th scope="col" style={{ ...headerCellStyle, width: "25%" }}>
                Status
              </th>
              <th scope="col" style={{ ...headerCellStyle, width: "14%" }}>
                Abnormal
              </th>
              <th scope="col" style={{ ...headerCellStyle, width: 44 }}>
                <span style={srOnly}>Open</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    padding: "60px 20px",
                    textAlign: "center",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  {emptyMessage ?? "No orders to display."}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <OrderOverviewRow key={row.id_order} row={row} onOpen={onOpenOrder} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {footer ? (
        <div style={{ borderTop: "1px solid var(--color-border)" }}>{footer}</div>
      ) : null}
    </div>
  );
}
