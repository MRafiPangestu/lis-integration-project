import type { ReactNode } from "react";
import { Header } from "./Header";
import { FilterBar, type FilterBarProps } from "./FilterBar";

export interface AppShellProps {
  sidebar: ReactNode;
  searchProps: FilterBarProps;
  children: ReactNode;
}

// M8.5 two-column shell. Replaces MainLayout's role: Sidebar on the left,
// Header + global MRN lookup + the active view on the right. StickyStatusBar is
// retired from the shell (superseded by the sidebar); its file is retained.
export function AppShell({ sidebar, searchProps, children }: AppShellProps) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "stretch" }}>
      {sidebar}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <Header />
        <div
          style={{
            backgroundColor: "var(--color-surface)",
            borderBottom: "1px solid var(--color-border)",
            padding: "var(--space-3) var(--space-4)",
          }}
        >
          <FilterBar {...searchProps} />
        </div>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
