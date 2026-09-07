import React from "react";

export const Header: React.FC = () => {
  return (
    <header style={{
      backgroundColor: "var(--color-surface)",
      borderBottom: "1px solid var(--color-border)",
      padding: "var(--space-3) var(--space-4)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }}>
      <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>LIS Middleware</h1>
      <div style={{ color: "var(--color-text-secondary)", fontSize: "0.875rem" }}>
        Dashboard
      </div>
    </header>
  );
};
