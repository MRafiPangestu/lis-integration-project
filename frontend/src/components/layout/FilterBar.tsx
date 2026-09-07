import React from "react";

export const FilterBar: React.FC = () => {
  return (
    <div style={{
      backgroundColor: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      borderRadius: "4px",
      padding: "var(--space-3)",
      display: "flex",
      gap: "var(--space-3)",
      flexWrap: "wrap"
    }}>
      <div style={{ color: "var(--color-text-secondary)", fontSize: "0.875rem" }}>
        [ All Instruments ▼ ] [ All Status ▼ ] [ Date ▼ ] [ Search Patient / RM ]
      </div>
    </div>
  );
};
