import React from "react";
import type { InstrumentStatusResponse } from "../../types/api";

export interface StickyStatusBarProps {
  instrumentStatuses: InstrumentStatusResponse[] | null;
  loading: boolean;
  error: Error | null;
  onRetry: () => Promise<void>;
}

function statusColor(status: string): string {
  switch (status.toUpperCase()) {
    case "CONNECTED":
      return "var(--color-flag-normal)";
    case "RECONNECTING":
    case "DISCONNECTED":
      return "var(--color-flag-low)";
    default:
      return "var(--color-text-secondary)";
  }
}

export const StickyStatusBar: React.FC<StickyStatusBarProps> = ({
  instrumentStatuses,
  loading,
  error,
  onRetry,
}) => {
  return (
    <div style={{
      backgroundColor: "var(--color-surface)",
      borderBottom: "1px solid var(--color-border)",
      padding: "var(--space-2) var(--space-4)",
      position: "sticky",
      top: 0,
      zIndex: 10,
      display: "flex",
      gap: "var(--space-4)",
      fontSize: "0.875rem",
      overflowX: "auto"
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
        <span style={{ color: "var(--color-text-secondary)" }}>Instruments:</span>
        {loading ? (
          <span>Loading status...</span>
        ) : error ? (
          <>
            <span role="alert">Unable to load instrument status.</span>
            <button
              type="button"
              onClick={() => {
                void onRetry();
              }}
              style={{
                background: "none",
                border: 0,
                color: "var(--color-primary)",
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
              }}
            >
              Retry
            </button>
          </>
        ) : instrumentStatuses && instrumentStatuses.length > 0 ? (
          instrumentStatuses.map((instrument) => {
            const status = instrument.connection_status.trim() || "UNKNOWN";

            return (
              <span
                key={instrument.id_instrument}
                aria-label={`${instrument.nama_mesin} status: ${status}`}
                style={{
                  alignItems: "center",
                  display: "inline-flex",
                  gap: "var(--space-1)",
                  marginRight: "var(--space-3)",
                }}
              >
                <span aria-hidden="true" style={{ color: statusColor(status) }}>●</span>
                <span>{instrument.nama_mesin}: {status}</span>
              </span>
            );
          })
        ) : (
          <span>No instrument status available.</span>
        )}
      </div>
    </div>
  );
};
