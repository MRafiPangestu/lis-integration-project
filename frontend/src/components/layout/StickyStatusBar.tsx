import React from "react";

export const StickyStatusBar: React.FC = () => {
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
        <span style={{ color: "var(--color-flag-normal)" }}>● Connected</span>
      </div>
    </div>
  );
};
