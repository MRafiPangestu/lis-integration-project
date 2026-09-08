import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { last7DaysRange, todayRange, yesterdayRange } from "./dateRange";

export interface DateRangeFilterProps {
  dateFrom: string;
  dateTo: string;
  onChange: (dateFrom: string, dateTo: string) => void;
}

const fieldStyle: CSSProperties = {
  border: "1px solid var(--color-border)",
  borderRadius: "4px",
  color: "var(--color-text-primary)",
  fontFamily: "var(--font-clinical)",
  padding: "var(--space-2) var(--space-3)",
};

const presetStyle: CSSProperties = {
  background: "none",
  border: "1px solid var(--color-border)",
  borderRadius: "4px",
  color: "var(--color-primary)",
  cursor: "pointer",
  fontSize: "0.8rem",
  padding: "var(--space-1) var(--space-3)",
};

export function DateRangeFilter({ dateFrom, dateTo, onChange }: DateRangeFilterProps) {
  const [draftFrom, setDraftFrom] = useState(dateFrom);
  const [draftTo, setDraftTo] = useState(dateTo);

  const invalid = useMemo(
    () => draftFrom !== "" && draftTo !== "" && draftTo <= draftFrom,
    [draftFrom, draftTo],
  );

  const commit = (nextFrom: string, nextTo: string) => {
    setDraftFrom(nextFrom);
    setDraftTo(nextTo);
    // Only a valid half-open range reaches the parent; an invalid range
    // suppresses the request (the API 422 is only a fallback).
    if (nextFrom !== "" && nextTo !== "" && nextTo > nextFrom) {
      onChange(nextFrom, nextTo);
    }
  };

  const applyPreset = (range: [string, string]) => commit(range[0], range[1]);

  return (
    <div
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "4px",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "flex-end",
        gap: "var(--space-3)",
        padding: "var(--space-3)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label htmlFor="overview-date-from" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
          From
        </label>
        <input
          id="overview-date-from"
          type="datetime-local"
          value={draftFrom}
          onChange={(event) => commit(event.target.value, draftTo)}
          style={fieldStyle}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label htmlFor="overview-date-to" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
          To
        </label>
        <input
          id="overview-date-to"
          type="datetime-local"
          value={draftTo}
          onChange={(event) => commit(draftFrom, event.target.value)}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? "overview-date-error" : undefined}
          style={fieldStyle}
        />
      </div>

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <button type="button" style={presetStyle} onClick={() => applyPreset(todayRange())}>
          Today
        </button>
        <button
          type="button"
          style={presetStyle}
          onClick={() => applyPreset(yesterdayRange())}
        >
          Yesterday
        </button>
        <button
          type="button"
          style={presetStyle}
          onClick={() => applyPreset(last7DaysRange())}
        >
          Last 7 days
        </button>
      </div>

      {invalid ? (
        <p
          id="overview-date-error"
          role="alert"
          style={{ color: "var(--color-flag-high)", fontSize: "0.8rem", width: "100%" }}
        >
          "To" must be after "From".
        </p>
      ) : null}
    </div>
  );
}
