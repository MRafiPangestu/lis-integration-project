export interface OverviewHeaderProps {
  instrumentName: string;
  total: number | null;
  loading: boolean;
}

export function OverviewHeader({ instrumentName, total, loading }: OverviewHeaderProps) {
  const subtitle =
    total === null
      ? loading
        ? "Loading…"
        : ""
      : `${total} order${total === 1 ? "" : "s"}`;

  return (
    <div>
      <h2 style={{ fontSize: "1.1rem", fontWeight: 600 }}>{instrumentName}</h2>
      {subtitle ? (
        <p style={{ color: "var(--color-text-secondary)", fontSize: "0.85rem" }}>
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
