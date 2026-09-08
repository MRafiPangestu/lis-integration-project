import { useState } from "react";
import { AppShell } from "./components/layout/AppShell";
import { Sidebar } from "./components/layout/Sidebar";
import { OrderDetailView } from "./components/detail/OrderDetailView";
import { OrderOverviewView } from "./components/overview/OrderOverviewView";
import type { OverviewDetailTarget } from "./components/overview/OrderOverviewView";
import { todayRange } from "./components/overview/dateRange";
import { EmptyState } from "./components/status/EmptyState";
import { ErrorState } from "./components/status/ErrorState";
import { LoadingState } from "./components/status/LoadingState";
import { useInstruments } from "./hooks/useInstruments";

function App() {
  const instruments = useInstruments();

  const [activeInstrumentId, setActiveInstrumentId] = useState<number | null>(null);
  const [detailTarget, setDetailTarget] = useState<OverviewDetailTarget | null>(null);
  const [initialRange] = useState(todayRange);
  const [dateFrom, setDateFrom] = useState(initialRange[0]);
  const [dateTo, setDateTo] = useState(initialRange[1]);
  const [page, setPage] = useState(1);

  // Legacy MRN-search path (kept for backwards-compatible detail behaviour).
  const [searchInput, setSearchInput] = useState("");
  const [searchNomorRm, setSearchNomorRm] = useState<string | null>(null);
  const [searchGeneration, setSearchGeneration] = useState(0);

  // Default selection: the user's explicit choice, otherwise the first
  // instrument the API returns (lowest id_instrument). Derived, never a
  // hardcoded id and never stored via an effect.
  const selectedInstrumentId =
    activeInstrumentId ?? instruments.data?.[0]?.id_instrument ?? null;

  const handleSelectInstrument = (instrumentId: number) => {
    setActiveInstrumentId(instrumentId);
    setDetailTarget(null);
    setSearchNomorRm(null);
    setPage(1);
  };

  const handleDateChange = (nextFrom: string, nextTo: string) => {
    setDateFrom(nextFrom);
    setDateTo(nextTo);
    setPage(1);
  };

  const handleOpenOrder = (target: OverviewDetailTarget) => {
    setSearchNomorRm(null);
    setDetailTarget(target);
  };

  const handleSearchSubmit = () => {
    setDetailTarget(null);
    setSearchNomorRm(searchInput.trim() || null);
    setSearchGeneration((generation) => generation + 1);
  };

  const activeInstrument =
    instruments.data?.find((item) => item.id_instrument === selectedInstrumentId) ?? null;

  let view;
  if (detailTarget !== null) {
    view = (
      <OrderDetailView
        key={`order:${detailTarget.idOrder}`}
        nomorRm={detailTarget.nomorRm}
        initialVisitId={detailTarget.idVisit}
        initialOrderId={detailTarget.idOrder}
        onBack={() => setDetailTarget(null)}
      />
    );
  } else if (searchNomorRm !== null) {
    view = (
      <OrderDetailView
        key={`search:${searchGeneration}`}
        nomorRm={searchNomorRm}
        onBack={() => setSearchNomorRm(null)}
      />
    );
  } else if (instruments.loading && instruments.data === null) {
    view = <LoadingState message="Loading instruments…" />;
  } else if (instruments.error && instruments.data === null) {
    view = (
      <ErrorState
        error={instruments.error}
        message="Unable to load instruments. Please try again."
        onRetry={instruments.refetch}
        title="Instruments unavailable"
      />
    );
  } else if (selectedInstrumentId === null || activeInstrument === null) {
    view = (
      <EmptyState
        title="No instrument selected"
        message="Select an instrument to view its worklist."
      />
    );
  } else {
    view = (
      <OrderOverviewView
        instrumentId={selectedInstrumentId}
        instrumentName={activeInstrument.nama_mesin}
        dateFrom={dateFrom}
        dateTo={dateTo}
        page={page}
        onDateChange={handleDateChange}
        onPageChange={setPage}
        onOpenOrder={handleOpenOrder}
      />
    );
  }

  return (
    <AppShell
      sidebar={
        <Sidebar
          instruments={instruments.data}
          loading={instruments.loading}
          error={instruments.error}
          onRetry={instruments.refetch}
          activeInstrumentId={selectedInstrumentId}
          onSelect={handleSelectInstrument}
        />
      }
      searchProps={{
        searchValue: searchInput,
        onSearchValueChange: setSearchInput,
        onSearchSubmit: handleSearchSubmit,
      }}
    >
      {view}
    </AppShell>
  );
}

export default App;
