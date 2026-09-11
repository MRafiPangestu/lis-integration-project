import type { ReactNode } from "react";
import { Header } from "./Header";
import type { InstrumentStatusResponse, UserPublic } from "../../types/api";

export interface AppShellProps {
  sidebar: ReactNode;
  activeInstrument?: InstrumentStatusResponse | null;
  sidebarExpanded?: boolean;
  onToggleSidebar?: () => void;
  user?: UserPublic | null;
  onLogout?: () => void;
  children: ReactNode;
}

// Two-column shell: navy Sidebar on the left; instrument-aware Header (with the
// sidebar toggle) plus the active view on the right. The MRN search now lives in
// the overview toolbar, not the shell.
export function AppShell({
  sidebar,
  activeInstrument,
  sidebarExpanded,
  onToggleSidebar,
  user,
  onLogout,
  children,
}: AppShellProps) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "stretch" }}>
      {sidebar}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <Header
          activeInstrument={activeInstrument}
          sidebarExpanded={sidebarExpanded}
          onToggleSidebar={onToggleSidebar}
          user={user}
          onLogout={onLogout}
        />
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
