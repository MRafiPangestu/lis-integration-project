export type MainView = "worklist" | "unlinked";

export interface MainViewSwitchProps {
  active: MainView;
  onChange: (view: MainView) => void;
}

const OPTIONS: { view: MainView; label: string }[] = [
  { view: "worklist", label: "Order worklist" },
  { view: "unlinked", label: "Unlinked instrument results" },
];

// Navigation between the M8.4 order worklist and the XN-550 unlinked
// instrument results (contract C.1). Navigation only — it changes nothing.
export function MainViewSwitch({ active, onChange }: MainViewSwitchProps) {
  return (
    <nav aria-label="Instrument views" style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
      {OPTIONS.map((option) => {
        const isActive = option.view === active;
        return (
          <button
            key={option.view}
            type="button"
            className={isActive ? "lis-btn lis-btn--primary" : "lis-btn lis-btn--secondary"}
            aria-current={isActive ? "page" : undefined}
            onClick={() => onChange(option.view)}
          >
            {option.label}
          </button>
        );
      })}
    </nav>
  );
}
