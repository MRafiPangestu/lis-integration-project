export interface ResultFlagProps {
  flag: string | null
}

interface KnownFlagPresentation {
  description: string
  label: string
  symbol: string
  color: string
}

const knownFlags: Record<string, KnownFlagPresentation> = {
  H: {
    description: "High",
    label: "H",
    symbol: "▲",
    color: "var(--color-flag-high)",
  },
  HIGH: {
    description: "High",
    label: "H",
    symbol: "▲",
    color: "var(--color-flag-high)",
  },
  CRITICAL: {
    description: "Critical high",
    label: "H",
    symbol: "▲",
    color: "var(--color-flag-high)",
  },
  L: {
    description: "Low",
    label: "L",
    symbol: "▼",
    color: "var(--color-flag-low)",
  },
  LOW: {
    description: "Low",
    label: "L",
    symbol: "▼",
    color: "var(--color-flag-low)",
  },
  WARNING: {
    description: "Low warning",
    label: "L",
    symbol: "▼",
    color: "var(--color-flag-low)",
  },
  N: {
    description: "Normal",
    label: "N",
    symbol: "✓",
    color: "var(--color-flag-normal)",
  },
  NORMAL: {
    description: "Normal",
    label: "N",
    symbol: "✓",
    color: "var(--color-flag-normal)",
  },
}

const flagStyle = {
  alignItems: "center",
  border: "1px solid currentColor",
  borderRadius: "var(--radius-sm)",
  display: "inline-flex",
  gap: "var(--space-1)",
  padding: "var(--space-1) var(--space-2)",
} as const

export function ResultFlag({ flag }: ResultFlagProps) {
  const rawFlag = flag?.trim() ?? ""

  if (rawFlag.length === 0) {
    return (
      <span
        role="img"
        aria-label="No abnormality flag provided"
        style={{ color: "var(--color-text-secondary)" }}
      >
        —
      </span>
    )
  }

  const presentation = knownFlags[rawFlag.toUpperCase()]

  if (!presentation) {
    return (
      <span
        role="img"
        aria-label={`Unknown result flag: ${rawFlag}`}
        style={{ ...flagStyle, color: "var(--color-text-secondary)" }}
      >
        <span aria-hidden="true">?</span>
        <span>{rawFlag}</span>
      </span>
    )
  }

  return (
    <span
      role="img"
      aria-label={`${presentation.description} result flag`}
      style={{ ...flagStyle, color: presentation.color }}
    >
      <span aria-hidden="true">{presentation.symbol}</span>
      <span>{presentation.label}</span>
    </span>
  )
}
