import type { CSSProperties } from "react";

export interface FilterBarProps {
  searchValue: string;
  onSearchValueChange: (value: string) => void;
  onSearchSubmit: () => void;
}

const srOnly: CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
};

const searchGlyph = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

export function FilterBar({
  searchValue,
  onSearchValueChange,
  onSearchSubmit,
}: FilterBarProps) {
  return (
    <form
      aria-label="Patient search"
      onSubmit={(event) => {
        event.preventDefault();
        onSearchSubmit();
      }}
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        width: "100%",
        minWidth: 0,
      }}
    >
      <label htmlFor="patient-search" style={srOnly}>
        Search Patient / RM
      </label>
      <button
        type="submit"
        aria-label="Search"
        style={{
          position: "absolute",
          left: 12,
          top: "50%",
          transform: "translateY(-50%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          color: "var(--color-text-secondary)",
        }}
      >
        {searchGlyph}
      </button>
      <input
        className="lis-input"
        id="patient-search"
        name="patient-search"
        onChange={(event) => onSearchValueChange(event.target.value)}
        placeholder="Enter medical record number"
        type="search"
        value={searchValue}
        style={{
          width: "100%",
          minWidth: 0,
          height: 36,
          border: "1px solid var(--color-border-input)",
          borderRadius: "var(--radius-md)",
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-clinical)",
          fontSize: "0.8125rem",
          padding: "8px 12px 8px 36px",
        }}
      />
    </form>
  );
}
