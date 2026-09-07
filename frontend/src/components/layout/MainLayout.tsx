import React from "react";
import { Header } from "./Header";
import { StickyStatusBar, type StickyStatusBarProps } from "./StickyStatusBar";
import { FilterBar, type FilterBarProps } from "./FilterBar";

interface MainLayoutProps {
  children: React.ReactNode;
  filterBarProps: FilterBarProps;
  stickyStatusBarProps: StickyStatusBarProps;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  filterBarProps,
  stickyStatusBarProps,
}) => {
  return (
    <div className="app-container">
      <Header />
      <StickyStatusBar {...stickyStatusBarProps} />
      <main className="main-content">
        <FilterBar {...filterBarProps} />
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {children}
        </div>
      </main>
    </div>
  );
};
