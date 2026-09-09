import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { allRange, last7DaysRange, todayRange, yesterdayRange } from "./dateRange";

export interface DateRangeFilterProps {
  dateFrom: string;
  dateTo: string;
  onChange: (dateFrom: string, dateTo: string) => void;
}

const srOnly: CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
};

const inputStyle: CSSProperties = {
  border: "1px solid var(--color-border-input)",
  borderRadius: "var(--radius-sm)",
  color: "var(--color-text-primary)",
  fontFamily: "var(--font-clinical)",
  fontSize: "0.8125rem",
  padding: "var(--space-1) var(--space-2)",
};

function presetButtonStyle(active: boolean, first: boolean, last: boolean): CSSProperties {
  return {
    background: active ? "var(--color-primary)" : "var(--color-surface)",
    border: "1px solid var(--color-border-input)",
    borderLeft: first ? "1px solid var(--color-border-input)" : "none",
    borderTopLeftRadius: first ? "var(--radius-sm)" : undefined,
    borderBottomLeftRadius: first ? "var(--radius-sm)" : undefined,
    borderTopRightRadius: last ? "var(--radius-sm)" : undefined,
    borderBottomRightRadius: last ? "var(--radius-sm)" : undefined,
    color: active ? "var(--color-surface)" : "var(--color-text-secondary)",
    cursor: "pointer",
    fontSize: "0.75rem",
    padding: "var(--space-1) var(--space-3)",
  };
}

type PresetKey = "all" | "today" | "yesterday" | "last7";

const PRESETS: { key: PresetKey; label: string; range: () => [string, string] }[] = [
  { key: "all", label: "All", range: allRange },
  { key: "today", label: "Today", range: todayRange },
  { key: "yesterday", label: "Yesterday", range: yesterdayRange },
  { key: "last7", label: "Last 7 days", range: last7DaysRange },
];

export function DateRangeFilter({ dateFrom, dateTo, onChange }: DateRangeFilterProps) {
  const [draftFrom, setDraftFrom] = useState(dateFrom);
  const [draftTo, setDraftTo] = useState(dateTo);

  const invalid = useMemo(
    () => draftFrom !== "" && draftTo !== "" && draftTo <= draftFrom,
    [draftFrom, draftTo],
  );

  // Derived, for styling only — which preset the current draft matches.
  const activePreset = useMemo(() => {
    const matches = (range: [string, string]) =>
      range[0] === draftFrom && range[1] === draftTo;
    if (matches(allRange())) return "all";
    if (matches(todayRange())) return "today";
    if (matches(yesterdayRange())) return "yesterday";
    if (matches(last7DaysRange())) return "last7";
    return null;
  }, [draftFrom, draftTo]);

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
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: "var(--space-3)",
      }}
    >
      <div style={{ display: "flex" }}>
        {PRESETS.map((preset, index) => (
          <button
            key={preset.key}
            type="button"
            onClick={() => applyPreset(preset.range())}
            style={presetButtonStyle(
              activePreset === preset.key,
              index === 0,
              index === PRESETS.length - 1,
            )}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {activePreset === "all" ? (
        <span style={{ color: "var(--color-text-secondary)", fontSize: "0.75rem" }}>
          All dates · every order for this instrument
        </span>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <label htmlFor="overview-date-from" style={srOnly}>
            From
          </label>
          <input
            className="lis-input"
            id="overview-date-from"
            type="datetime-local"
            value={draftFrom}
            onChange={(event) => commit(event.target.value, draftTo)}
            style={inputStyle}
          />
          <span style={{ color: "var(--color-text-secondary)", fontSize: "0.8125rem" }}>to</span>
          <label htmlFor="overview-date-to" style={srOnly}>
            To
          </label>
          <input
            className="lis-input"
            id="overview-date-to"
            type="datetime-local"
            value={draftTo}
            onChange={(event) => commit(draftFrom, event.target.value)}
            aria-invalid={invalid || undefined}
            aria-describedby={invalid ? "overview-date-error" : undefined}
            style={inputStyle}
          />
        </div>
      )}

      {invalid ? (
        <p
          id="overview-date-error"
          role="alert"
          style={{ color: "var(--color-flag-high)", fontSize: "0.75rem", width: "100%" }}
        >
          "To" must be after "From".
        </p>
      ) : null}
    </div>
  );
}
