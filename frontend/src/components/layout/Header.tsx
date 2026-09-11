import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { InstrumentStatusResponse, UserPublic } from "../../types/api";

export interface HeaderProps {
  activeInstrument?: InstrumentStatusResponse | null;
  sidebarExpanded?: boolean;
  onToggleSidebar?: () => void;
  user?: UserPublic | null;
  onLogout?: () => void;
}

type HeaderLayout = "wide" | "mid" | "narrow";

function readHeaderLayout(): HeaderLayout {
  if (typeof window === "undefined") return "wide";
  if (window.matchMedia("(max-width: 900px)").matches) return "narrow";
  if (window.matchMedia("(max-width: 1099px)").matches) return "mid";
  return "wide";
}

// Local media hook mirroring Sidebar.useIsNarrow(). No global CSS class, no new
// dependency. Gates metadata visibility and the sidebar toggle; it no longer
// sizes a search field (the search moved to the overview toolbar).
function useHeaderLayout(): HeaderLayout {
  const [layout, setLayout] = useState<HeaderLayout>(readHeaderLayout);

  useEffect(() => {
    const narrow = window.matchMedia("(max-width: 900px)");
    const mid = window.matchMedia("(max-width: 1099px)");
    const update = () => setLayout(readHeaderLayout());
    update();
    narrow.addEventListener("change", update);
    mid.addEventListener("change", update);
    return () => {
      narrow.removeEventListener("change", update);
      mid.removeEventListener("change", update);
    };
  }, []);

  return layout;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

// Display only — last_status_at is a server-local naive timestamp.
function formatStatusTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return (
    `${pad(parsed.getDate())}/${pad(parsed.getMonth() + 1)} ` +
    `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  );
}

const headerStyle: CSSProperties = {
  height: 64,
  flexShrink: 0,
  minWidth: 0,
  backgroundColor: "var(--color-surface)",
  borderBottom: "1px solid var(--color-border)",
  padding: "0 var(--space-6)",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "var(--space-4)",
};

// D11 fix: nowrap + clip + ellipsis so a long line truncates instead of spilling.
const metadataLineBase: CSSProperties = {
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const toggleGlyph = (
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
    <path d="M3 12h18M3 6h18M3 18h18" />
  </svg>
);

export function Header({
  activeInstrument,
  sidebarExpanded,
  onToggleSidebar,
  user,
  onLogout,
}: HeaderProps) {
  const layout = useHeaderLayout();
  const showMetadata = layout !== "narrow";
  const showToggle = Boolean(onToggleSidebar) && layout !== "narrow";

  const title = activeInstrument?.nama_mesin ?? "LIS Server";

  const protocolLine = [activeInstrument?.protokol, activeInstrument?.tipe_koneksi]
    .filter((part): part is string => Boolean(part))
    .join(" · ");

  return (
    <header style={headerStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          flex: "1 1 auto",
          minWidth: 0,
        }}
      >
        {showToggle ? (
          <button
            type="button"
            onClick={onToggleSidebar}
            aria-label="Toggle instrument sidebar"
            aria-expanded={sidebarExpanded ?? true}
            aria-controls="instrument-sidebar"
            style={{
              flexShrink: 0,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 32,
              height: 32,
              marginRight: "var(--space-3)",
              background: "none",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-text-secondary)",
              cursor: "pointer",
            }}
          >
            {toggleGlyph}
          </button>
        ) : null}
        <div style={{ minWidth: 0, flex: "1 1 auto" }}>
          <h1
            title={title}
            style={{
              fontSize: "1.125rem",
              fontWeight: 600,
              color: "var(--color-text-primary)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {title}
          </h1>
        </div>
      </div>

      {showMetadata && (protocolLine || activeInstrument?.last_status_at) ? (
        <div style={{ textAlign: "right", minWidth: 0, flex: "0 1 auto" }}>
          {protocolLine ? (
            <div
              style={{
                ...metadataLineBase,
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "var(--color-text-primary)",
              }}
            >
              {protocolLine}
            </div>
          ) : null}
          {activeInstrument?.last_status_at ? (
            <div
              style={{
                ...metadataLineBase,
                fontSize: "0.6875rem",
                color: "var(--color-text-secondary)",
              }}
            >
              Last status: {formatStatusTime(activeInstrument.last_status_at)}
            </div>
          ) : null}
        </div>
      ) : null}

      {user ? (
        <div
          style={{
            alignItems: "center",
            display: "flex",
            flexShrink: 0,
            gap: "var(--space-3)",
            marginLeft: "var(--space-4)",
          }}
        >
          {showMetadata ? (
            <span
              style={{
                color: "var(--color-text-secondary)",
                fontSize: "0.75rem",
                whiteSpace: "nowrap",
              }}
            >
              {user.nama_lengkap}
            </span>
          ) : null}
          <button
            className="lis-btn lis-btn--secondary"
            onClick={onLogout}
            style={{ height: 32, padding: "0 var(--space-3)" }}
            type="button"
          >
            Sign out
          </button>
        </div>
      ) : null}
    </header>
  );
}
