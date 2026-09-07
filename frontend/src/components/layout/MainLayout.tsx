import React from "react";
import { Header } from "./Header";
import { StickyStatusBar } from "./StickyStatusBar";
import { FilterBar } from "./FilterBar";

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="app-container">
      <Header />
      <StickyStatusBar />
      <main className="main-content">
        <FilterBar />
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {children}
        </div>
      </main>
    </div>
  );
};
