import type { CSSProperties } from "react";
import { presentInstrumentFlag, type FlagTone } from "./presentation";

export interface InstrumentFlagProps {
  flag: string | null;
}

const TONE_COLOR: Record<FlagTone, string> = {
  high: "var(--color-flag-high)",
  low: "var(--color-flag-low)",
  normal: "var(--color-flag-normal)",
  unknown: "var(--color-text-secondary)",
  none: "var(--color-text-secondary)",
};

const badgeStyle: CSSProperties = {
  alignItems: "center",
  border: "1px solid currentColor",
  borderRadius: "var(--radius-sm)",
  display: "inline-flex",
  gap: "var(--space-1)",
  padding: "var(--space-1) var(--space-2)",
  whiteSpace: "nowrap",
};

// XN-550 instrument flag (contract C.3). Exact, case-sensitive H / L / N are the
// only known values; every other value is shown verbatim as unknown. This is
// not the clinical ResultFlag and shares none of its mappings.
export function InstrumentFlag({ flag }: InstrumentFlagProps) {
  const presentation = presentInstrumentFlag(flag);

  if (presentation.tone === "none") {
    return (
      <span role="img" aria-label={presentation.accessibleLabel} style={{ color: TONE_COLOR.none }}>
        {presentation.symbol}
      </span>
    );
  }

  return (
    <span
      role="img"
      aria-label={presentation.accessibleLabel}
      title={presentation.accessibleLabel}
      style={{ ...badgeStyle, color: TONE_COLOR[presentation.tone] }}
    >
      <span aria-hidden="true">{presentation.symbol}</span>
      <span>{presentation.text}</span>
    </span>
  );
}
