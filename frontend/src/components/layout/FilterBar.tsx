import React from "react";

export interface FilterBarProps {
  searchValue: string;
  onSearchValueChange: (value: string) => void;
  onSearchSubmit: () => void;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  searchValue,
  onSearchValueChange,
  onSearchSubmit,
}) => {
  return (
    <form
      aria-label="Patient search"
      onSubmit={(event) => {
        event.preventDefault();
        onSearchSubmit();
      }}
      style={{
        alignItems: "end",
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "4px",
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--space-3)",
        padding: "var(--space-3)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label htmlFor="patient-search" style={{ fontSize: "0.875rem", fontWeight: 600 }}>
          Search Patient / RM
        </label>
        <input
          id="patient-search"
          name="patient-search"
          onChange={(event) => onSearchValueChange(event.target.value)}
          placeholder="Enter medical record number"
          type="search"
          value={searchValue}
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: "4px",
            color: "var(--color-text-primary)",
            fontFamily: "var(--font-clinical)",
            minWidth: "280px",
            padding: "var(--space-2) var(--space-3)",
          }}
        />
      </div>
      <button
        type="submit"
        style={{
          backgroundColor: "var(--color-primary)",
          border: "1px solid var(--color-primary)",
          borderRadius: "4px",
          color: "var(--color-surface)",
          cursor: "pointer",
          padding: "var(--space-2) var(--space-4)",
        }}
      >
        Search
      </button>
    </form>
  );
};
