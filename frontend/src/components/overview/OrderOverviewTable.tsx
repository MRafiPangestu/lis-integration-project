import type { CSSProperties } from "react";
import type { OrderOverviewRow as OrderOverviewRowData } from "../../types/api";
import { OrderOverviewRow } from "./OrderOverviewRow";

export interface OrderOverviewTableProps {
  rows: OrderOverviewRowData[];
  onOpenOrder: (row: OrderOverviewRowData) => void;
}

const headerCellStyle: CSSProperties = {
  backgroundColor: "var(--color-surface-hover)",
  borderBottom: "1px solid var(--color-border)",
  fontSize: "0.78rem",
  fontWeight: 600,
  letterSpacing: "0.02em",
  padding: "var(--space-2) var(--space-3)",
  textAlign: "left",
  textTransform: "uppercase",
};

export function OrderOverviewTable({ rows, onOpenOrder }: OrderOverviewTableProps) {
  return (
    <div style={{ overflowX: "auto", width: "100%" }}>
      <table
        style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderCollapse: "collapse",
          width: "100%",
        }}
      >
        <thead>
          <tr>
            <th scope="col" style={headerCellStyle}>Patient</th>
            <th scope="col" style={headerCellStyle}>Order time</th>
            <th scope="col" style={headerCellStyle}>Status</th>
            <th scope="col" style={headerCellStyle}>Abnormal</th>
            <th scope="col" style={{ ...headerCellStyle, width: 44 }}>
              <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden" }}>
                Open
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <OrderOverviewRow key={row.id_order} row={row} onOpen={onOpenOrder} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
