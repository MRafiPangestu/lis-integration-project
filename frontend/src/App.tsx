import { MainLayout } from "./components/layout/MainLayout";

function App() {
  return (
    <MainLayout>
      <div style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "4px",
        padding: "var(--space-6)",
        textAlign: "center",
        color: "var(--color-text-secondary)"
      }}>
        Clinical Data View Placeholder
      </div>
    </MainLayout>
  );
}

export default App;
