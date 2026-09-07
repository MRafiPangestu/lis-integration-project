import { useEffect, useMemo, useState } from "react";
import { ApiError } from "./api/client";
import { PatientSummary } from "./components/display/PatientSummary";
import { ResultTable } from "./components/display/ResultTable";
import { TestRunSelector } from "./components/display/TestRunSelector";
import { VisitOrderSelector } from "./components/display/VisitOrderSelector";
import { EmptyState } from "./components/status/EmptyState";
import { ErrorState } from "./components/status/ErrorState";
import { LoadingState } from "./components/status/LoadingState";
import { MainLayout } from "./components/layout/MainLayout";
import { useInstruments } from "./hooks/useInstruments";
import { useOrderTestRuns } from "./hooks/useOrderTestRuns";
import { usePatientHistory } from "./hooks/usePatientHistory";
import type {
  HistoryOrderResponse,
  HistoryPatientResponse,
  HistoryVisitResponse,
  TestRunResponse,
} from "./types/api";

function timestamp(value: string | null | undefined): number | null {
  if (!value) return null;

  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function compareNewest(
  firstTime: string | null | undefined,
  firstId: number,
  secondTime: string | null | undefined,
  secondId: number,
): number {
  const firstTimestamp = timestamp(firstTime);
  const secondTimestamp = timestamp(secondTime);

  if (firstTimestamp !== null || secondTimestamp !== null) {
    if (firstTimestamp === null) return 1;
    if (secondTimestamp === null) return -1;
    if (firstTimestamp !== secondTimestamp) {
      return secondTimestamp - firstTimestamp;
    }
  }

  return secondId - firstId;
}

function sortVisits(visits: HistoryVisitResponse[]): HistoryVisitResponse[] {
  return [...visits].sort((first, second) =>
    compareNewest(
      first.waktu_kunjungan,
      first.id_visit,
      second.waktu_kunjungan,
      second.id_visit,
    ),
  );
}

function sortOrders(orders: HistoryOrderResponse[]): HistoryOrderResponse[] {
  return [...orders].sort((first, second) =>
    compareNewest(first.waktu_order, first.id_order, second.waktu_order, second.id_order),
  );
}

function sortTestRuns(testRuns: TestRunResponse[]): TestRunResponse[] {
  return [...testRuns].sort((first, second) => {
    if (first.is_final !== second.is_final) {
      return first.is_final ? -1 : 1;
    }

    if (first.run_sequence !== second.run_sequence) {
      return second.run_sequence - first.run_sequence;
    }

    return compareNewest(first.waktu_run, first.id_run, second.waktu_run, second.id_run);
  });
}

function defaultTestRunId(testRuns: TestRunResponse[]): number | null {
  return sortTestRuns(testRuns)[0]?.id_run ?? null;
}

function activeHistoryFor(
  data: HistoryPatientResponse | null,
  activeNomorRm: string | null,
): HistoryPatientResponse | null {
  return data && activeNomorRm && data.nomor_rm === activeNomorRm ? data : null;
}

function App() {
  const [searchInput, setSearchInput] = useState("");
  const [activeNomorRm, setActiveNomorRm] = useState<string | null>(null);
  const [selectedVisitId, setSelectedVisitId] = useState<number | null>(null);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [patientRequestStarted, setPatientRequestStarted] = useState(false);
  const [testRunRequestStarted, setTestRunRequestStarted] = useState(false);

  const patientHistory = usePatientHistory(activeNomorRm);
  const orderTestRuns = useOrderTestRuns(selectedOrderId);
  const instruments = useInstruments();

  const activeHistory = activeHistoryFor(patientHistory.data, activeNomorRm);
  const sortedVisits = useMemo(
    () => (activeHistory ? sortVisits(activeHistory.visits) : []),
    [activeHistory],
  );
  const selectedVisit = useMemo(
    () => sortedVisits.find((visit) => visit.id_visit === selectedVisitId) ?? null,
    [selectedVisitId, sortedVisits],
  );
  const sortedOrders = useMemo(
    () => (selectedVisit ? sortOrders(selectedVisit.orders) : []),
    [selectedVisit],
  );
  const selectedOrder = useMemo(
    () => sortedOrders.find((order) => order.id_order === selectedOrderId) ?? null,
    [selectedOrderId, sortedOrders],
  );
  const activeTestRuns = useMemo(
    () => {
      if (selectedOrderId === null || orderTestRuns.data === null) return null;
      return orderTestRuns.data.filter((testRun) => testRun.id_order === selectedOrderId);
    },
    [orderTestRuns.data, selectedOrderId],
  );
  const selectedTestRun = useMemo(
    () => activeTestRuns?.find((testRun) => testRun.id_run === selectedRunId) ?? null,
    [activeTestRuns, selectedRunId],
  );

  useEffect(() => {
    if (activeNomorRm === null) {
      setPatientRequestStarted(false);
    } else if (patientHistory.loading) {
      setPatientRequestStarted(true);
    }
  }, [activeNomorRm, patientHistory.loading]);

  useEffect(() => {
    if (activeHistory === null) return;

    setSelectedVisitId((currentVisitId) => {
      if (sortedVisits.some((visit) => visit.id_visit === currentVisitId)) {
        return currentVisitId;
      }

      return sortedVisits[0]?.id_visit ?? null;
    });
  }, [activeHistory, sortedVisits]);

  useEffect(() => {
    setSelectedOrderId((currentOrderId) => {
      if (sortedOrders.some((order) => order.id_order === currentOrderId)) {
        return currentOrderId;
      }

      return sortedOrders[0]?.id_order ?? null;
    });
  }, [sortedOrders]);

  useEffect(() => {
    setSelectedRunId(null);
    setTestRunRequestStarted(false);
  }, [selectedOrderId]);

  useEffect(() => {
    if (orderTestRuns.loading) {
      setTestRunRequestStarted(true);
    }
  }, [orderTestRuns.loading]);

  useEffect(() => {
    if (selectedOrderId === null || activeTestRuns === null || orderTestRuns.loading) {
      if (selectedOrderId === null || activeTestRuns === null) {
        setSelectedRunId(null);
      }
      return;
    }

    setSelectedRunId((currentRunId) => {
      if (activeTestRuns.some((testRun) => testRun.id_run === currentRunId)) {
        return currentRunId;
      }

      return defaultTestRunId(activeTestRuns);
    });
  }, [activeTestRuns, orderTestRuns.loading, selectedOrderId]);

  const handleSearchSubmit = () => {
    const nextNomorRm = searchInput.trim() || null;

    setSelectedVisitId(null);
    setSelectedOrderId(null);
    setSelectedRunId(null);
    setPatientRequestStarted(false);
    setTestRunRequestStarted(false);
    setActiveNomorRm(nextNomorRm);

    if (nextNomorRm !== null && nextNomorRm === activeNomorRm) {
      void patientHistory.refetch();
    }
  };

  const handleVisitSelect = (visitId: number) => {
    if (!sortedVisits.some((visit) => visit.id_visit === visitId)) return;

    setSelectedVisitId(visitId);
    setSelectedOrderId(null);
    setSelectedRunId(null);
    setTestRunRequestStarted(false);
  };

  const handleOrderSelect = (orderId: number) => {
    if (!sortedOrders.some((order) => order.id_order === orderId)) return;

    setSelectedOrderId(orderId);
    setSelectedRunId(null);
    setTestRunRequestStarted(false);
  };

  const handleRunSelect = (runId: number) => {
    if (!activeTestRuns?.some((testRun) => testRun.id_run === runId)) return;
    setSelectedRunId(runId);
  };

  const patientNotFound =
    patientHistory.error instanceof ApiError && patientHistory.error.status === 404;

  const patientContent = activeNomorRm === null ? (
    <EmptyState
      title="No patient selected"
      message="Search for a patient to view laboratory history."
    />
  ) : !activeHistory && !patientRequestStarted ? (
    <LoadingState message="Loading patient history..." />
  ) : patientHistory.loading && !activeHistory ? (
    <LoadingState message="Loading patient history..." />
  ) : patientHistory.error && !activeHistory ? (
    <ErrorState
      error={patientHistory.error}
      message={
        patientNotFound
          ? "No patient was found for this medical record number."
          : "Unable to load patient history. Please try again."
      }
      onRetry={patientHistory.refetch}
      title={patientNotFound ? "Patient not found" : "Patient history unavailable"}
    />
  ) : activeHistory ? (
    <>
      <PatientSummary patient={activeHistory} visit={selectedVisit} order={selectedOrder} />

      {sortedVisits.length === 0 ? (
        <EmptyState
          title="No visits found"
          message="No visits were found for this patient."
        />
      ) : (
        <VisitOrderSelector
          disabled={patientHistory.loading}
          onOrderSelect={handleOrderSelect}
          onVisitSelect={handleVisitSelect}
          selectedOrderId={selectedOrderId}
          selectedVisitId={selectedVisitId}
          visits={sortedVisits}
        />
      )}

      {selectedVisit && sortedOrders.length === 0 ? (
        <EmptyState
          title="No orders found"
          message="No orders were found for this visit."
        />
      ) : null}

      {sortedVisits.length > 0 && selectedVisit === null ? (
        <EmptyState
          title="No visit selected"
          message="Select a visit to view its orders."
        />
      ) : null}

      {selectedVisit ? (
        selectedOrderId === null ? (
          <EmptyState
            title="No order selected"
            message="Select an order to view test runs."
          />
        ) : orderTestRuns.error && !testRunRequestStarted ? (
          <LoadingState message="Loading test runs..." />
        ) : orderTestRuns.loading || !testRunRequestStarted ? (
          <LoadingState message="Loading test runs..." />
        ) : orderTestRuns.error ? (
          <ErrorState
            error={orderTestRuns.error}
            message="Unable to load test runs. Please try again."
            onRetry={orderTestRuns.refetch}
            title="Test runs unavailable"
          />
        ) : activeTestRuns && activeTestRuns.length === 0 ? (
          <EmptyState
            title="No test runs found"
            message="No test runs were found for this order."
          />
        ) : activeTestRuns ? (
          <>
            <TestRunSelector
              disabled={orderTestRuns.loading}
              onSelect={handleRunSelect}
              selectedRunId={selectedRunId}
              testRuns={activeTestRuns}
            />
            {selectedTestRun === null ? (
              <EmptyState
                title="No test run selected"
                message="Select a test run to view results."
              />
            ) : selectedTestRun.results.length === 0 ? (
              <EmptyState
                title="No results found"
                message="No results were found for this test run."
              />
            ) : (
              <ResultTable results={selectedTestRun.results} />
            )}
          </>
        ) : null
      ) : null}
    </>
  ) : null;

  return (
    <MainLayout
      filterBarProps={{
        onSearchSubmit: handleSearchSubmit,
        onSearchValueChange: setSearchInput,
        searchValue: searchInput,
      }}
      stickyStatusBarProps={{
        error: instruments.error,
        instrumentStatuses: instruments.data,
        loading: instruments.loading,
        onRetry: instruments.refetch,
      }}
    >
      {patientContent}
    </MainLayout>
  );
}

export default App;
