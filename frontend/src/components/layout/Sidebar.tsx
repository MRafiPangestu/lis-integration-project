import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { InstrumentStatusResponse } from "../../types/api";

export interface SidebarProps {
  instruments: InstrumentStatusResponse[] | null;
  loading: boolean;
  error: Error | null;
  onRetry: () => Promise<void>;
  activeInstrumentId: number | null;
  onSelect: (instrumentId: number) => void;
}

// Mirrors StickyStatusBar.statusColor(): the same three-value vocabulary plus
// the backend's UNKNOWN fallback. StickyStatusBar itself is left untouched.
function statusColor(status: string): string {
  switch (status.trim().toUpperCase()) {
    case "CONNECTED":
      return "var(--color-flag-normal)";
    case "RECONNECTING":
    case "DISCONNECTED":
      return "var(--color-flag-low)";
    default:
      return "var(--color-text-secondary)";
  }
}

function normalizeStatus(status: string): string {
  return status.trim() || "UNKNOWN";
}

function useIsNarrow(): boolean {
  const query = "(max-width: 900px)";
  const [isNarrow, setIsNarrow] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setIsNarrow(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return isNarrow;
}

const asideBase: CSSProperties = {
  backgroundColor: "var(--color-sidebar-bg)",
  color: "var(--color-sidebar-text)",
  height: "100vh",
  position: "sticky",
  top: 0,
  flexShrink: 0,
  overflowY: "auto",
  display: "flex",
  flexDirection: "column",
};

export function Sidebar({
  instruments,
  loading,
  error,
  onRetry,
  activeInstrumentId,
  onSelect,
}: SidebarProps) {
  const isNarrow = useIsNarrow();
  const width = isNarrow ? 64 : 240;

  return (
    <aside
      aria-label="Instruments"
      style={{ ...asideBase, width }}
    >
      <div
        style={{
          padding: isNarrow ? "var(--space-3) 0" : "var(--space-4)",
          borderBottom: "1px solid var(--color-sidebar-hover)",
          textAlign: isNarrow ? "center" : "left",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: isNarrow ? "0.85rem" : "1rem" }}>
          {isNarrow ? "LIS" : "LIS Middleware"}
        </span>
      </div>

      <nav
        aria-label="Instrument list"
        style={{ display: "flex", flexDirection: "column", padding: "var(--space-2) 0" }}
      >
        {loading ? (
          <div style={{ padding: "var(--space-2) var(--space-4)" }}>
            {[0, 1, 2].map((row) => (
              <div
                key={row}
                aria-hidden="true"
                style={{
                  height: 32,
                  margin: "var(--space-2) 0",
                  borderRadius: 4,
                  backgroundColor: "var(--color-sidebar-hover)",
                  opacity: 0.6,
                }}
              />
            ))}
            <span style={{ position: "absolute", width: 1, height: 1, overflow: "hidden" }}>
              Loading instruments
            </span>
          </div>
        ) : error ? (
          <div
            role="alert"
            style={{
              padding: "var(--space-3) var(--space-4)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
              fontSize: "0.8rem",
            }}
          >
            <span>Unable to load instruments.</span>
            <button
              type="button"
              onClick={() => {
                void onRetry();
              }}
              style={{
                alignSelf: "flex-start",
                background: "none",
                border: "1px solid var(--color-sidebar-hover)",
                borderRadius: 4,
                color: "var(--color-sidebar-text)",
                cursor: "pointer",
                padding: "var(--space-1) var(--space-2)",
              }}
            >
              Retry
            </button>
          </div>
        ) : instruments && instruments.length > 0 ? (
          instruments.map((instrument) => {
            const isActive = instrument.id_instrument === activeInstrumentId;
            const status = normalizeStatus(instrument.connection_status);

            return (
              <button
                key={instrument.id_instrument}
                type="button"
                onClick={() => onSelect(instrument.id_instrument)}
                aria-current={isActive ? "page" : undefined}
                title={`${instrument.nama_mesin} — ${status}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  width: "100%",
                  textAlign: "left",
                  background: isActive ? "var(--color-sidebar-hover)" : "transparent",
                  border: "none",
                  borderLeft: isActive
                    ? "3px solid var(--color-primary)"
                    : "3px solid transparent",
                  color: "var(--color-sidebar-text)",
                  cursor: "pointer",
                  font: "inherit",
                  padding: isNarrow
                    ? "var(--space-3) 0"
                    : "var(--space-2) var(--space-4)",
                  justifyContent: isNarrow ? "center" : "flex-start",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{ color: statusColor(status), flexShrink: 0, fontSize: "0.8rem" }}
                >
                  ●
                </span>
                {isNarrow ? null : (
                  <span style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
                    <span
                      style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        fontSize: "0.9rem",
                        fontWeight: isActive ? 600 : 500,
                      }}
                    >
                      {instrument.nama_mesin}
                    </span>
                    <span
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--color-text-disabled)",
                      }}
                    >
                      {status}
                    </span>
                  </span>
                )}
              </button>
            );
          })
        ) : (
          <p style={{ padding: "var(--space-3) var(--space-4)", fontSize: "0.8rem" }}>
            No instruments available.
          </p>
        )}
      </nav>
    </aside>
  );
}
