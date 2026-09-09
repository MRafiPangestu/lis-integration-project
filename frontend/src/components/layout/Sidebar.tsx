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
  expanded?: boolean;
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
  transition: "width .2s ease",
};

const brandGlyph = (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </svg>
);

const skeletonRowStyle: CSSProperties = {
  height: 34,
  margin: "var(--space-2) 0",
  borderRadius: "var(--radius-md)",
  backgroundColor: "var(--color-sidebar-hover)",
  opacity: 0.6,
};

const srOnly: CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
};

export function Sidebar({
  instruments,
  loading,
  error,
  onRetry,
  activeInstrumentId,
  onSelect,
  expanded = true,
}: SidebarProps) {
  const isNarrow = useIsNarrow();
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  // ≤900px forces the rail; above it, the operator's toggle decides.
  const collapsed = isNarrow || !expanded;
  const width = collapsed ? 64 : 260;

  return (
    <aside id="instrument-sidebar" aria-label="Instruments" style={{ ...asideBase, width }}>
      <div
        style={{
          height: 64,
          flexShrink: 0,
          padding: "0 var(--space-4)",
          borderBottom: "1px solid var(--color-sidebar-hover)",
          display: "flex",
          alignItems: "center",
          overflow: "hidden",
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 32,
            height: 32,
            flexShrink: 0,
            borderRadius: "var(--radius-md)",
            backgroundColor: "var(--color-primary)",
            color: "var(--color-sidebar-active)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {brandGlyph}
        </span>
        {/* Text stays mounted so it can fade/slide with the width change instead
            of snapping in and out; max-width and margin collapse to zero so it
            never pushes the icon or spills past the 64px rail. */}
        <span
          className="lis-sidebar-brand"
          aria-hidden={collapsed || undefined}
          style={{
            display: "flex",
            flexDirection: "column",
            minWidth: 0,
            marginLeft: collapsed ? 0 : "var(--space-3)",
            maxWidth: collapsed ? 0 : "180px",
            overflow: "hidden",
            whiteSpace: "nowrap",
            opacity: collapsed ? 0 : 1,
          }}
        >
          <span
            style={{
              fontSize: "1.125rem",
              fontWeight: 700,
              color: "var(--color-sidebar-active)",
              lineHeight: 1.2,
            }}
          >
            LIS Server
          </span>
          <span style={{ fontSize: "0.75rem", color: "var(--color-sidebar-text)" }}>
            Marina Permata
          </span>
        </span>
      </div>

      <nav
        aria-label="Instrument list"
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          overflowY: "auto",
          padding: "var(--space-4) var(--space-3)",
        }}
      >
        {collapsed ? null : (
          <p
            style={{
              fontSize: "0.6875rem",
              fontWeight: 600,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "var(--color-sidebar-text)",
              marginBottom: "var(--space-3)",
              paddingLeft: "var(--space-3)",
            }}
          >
            Instruments
          </p>
        )}

        {loading ? (
          <div>
            {[0, 1, 2].map((row) => (
              <div key={row} aria-hidden="true" style={skeletonRowStyle} />
            ))}
            <span style={srOnly}>Loading instruments</span>
          </div>
        ) : error ? (
          <div
            role="alert"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-2)",
              padding: "var(--space-3)",
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
                borderRadius: "var(--radius-sm)",
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
            const isHovered = instrument.id_instrument === hoveredId;
            const status = normalizeStatus(instrument.connection_status);
            const dotColor = statusColor(status);
            const highlighted = isActive || isHovered;

            return (
              <button
                key={instrument.id_instrument}
                type="button"
                onClick={() => onSelect(instrument.id_instrument)}
                onMouseEnter={() => setHoveredId(instrument.id_instrument)}
                onMouseLeave={() =>
                  setHoveredId((current) =>
                    current === instrument.id_instrument ? null : current,
                  )
                }
                aria-current={isActive ? "page" : undefined}
                title={`${instrument.nama_mesin} — ${status}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-3)",
                  width: "100%",
                  textAlign: "left",
                  background: highlighted ? "var(--color-sidebar-hover)" : "transparent",
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  marginBottom: "var(--space-1)",
                  color: highlighted
                    ? "var(--color-sidebar-active)"
                    : "var(--color-sidebar-text)",
                  cursor: "pointer",
                  font: "inherit",
                  fontWeight: isActive ? 600 : 400,
                  padding: collapsed ? "var(--space-3) 0" : "10px var(--space-3)",
                  justifyContent: collapsed ? "center" : "flex-start",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 8,
                    height: 8,
                    flexShrink: 0,
                    borderRadius: "50%",
                    background: dotColor,
                    color: dotColor,
                    boxShadow:
                      isActive && status === "CONNECTED"
                        ? "0 0 6px currentColor"
                        : undefined,
                  }}
                />
                {collapsed ? (
                  <span style={srOnly}>
                    {instrument.nama_mesin} — {status}
                  </span>
                ) : (
                  <span style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
                    <span
                      style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        fontSize: "0.8125rem",
                      }}
                    >
                      {instrument.nama_mesin}
                    </span>
                    <span
                      style={{
                        fontSize: "0.6875rem",
                        textTransform: "uppercase",
                        color: "var(--color-sidebar-text)",
                        opacity: 0.8,
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
          <p style={{ padding: "var(--space-3)", fontSize: "0.8rem" }}>
            No instruments available.
          </p>
        )}
      </nav>
    </aside>
  );
}
