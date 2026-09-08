import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { PatientSummary } from "../display/PatientSummary";
import { ResultTable } from "../display/ResultTable";
import { TestRunSelector } from "../display/TestRunSelector";
import { VisitOrderSelector } from "../display/VisitOrderSelector";
import { EmptyState } from "../status/EmptyState";
import { ErrorState } from "../status/ErrorState";
import { LoadingState } from "../status/LoadingState";
import { FinalRunWorkflow } from "../workflow/FinalRunWorkflow";
import { SimrsSyncWorkflow } from "../workflow/SimrsSyncWorkflow";
import { useOrderTestRuns } from "../../hooks/useOrderTestRuns";
import { usePatientHistory } from "../../hooks/usePatientHistory";
import type {
  HistoryOrderResponse,
  HistoryPatientResponse,
  HistoryVisitResponse,
  TestRunResponse,
} from "../../types/api";

export interface OrderDetailViewProps {
  nomorRm: string;
  initialVisitId?: number | null;
  initialOrderId?: number | null;
  onBack?: () => void;
}

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

export function OrderDetailView({
  nomorRm,
  initialVisitId = null,
  initialOrderId = null,
  onBack,
}: OrderDetailViewProps) {
  // M8.5: the searched/clicked MRN arrives as a prop. Visit/order preselection
  // is seeded from props so the coordinating effects below *validate* the
  // selection instead of resetting it to the newest visit/order.
  const [selectedVisitId, setSelectedVisitId] = useState<number | null>(initialVisitId);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(initialOrderId);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [patientRequestStarted, setPatientRequestStarted] = useState(false);
  const [testRunRequestStarted, setTestRunRequestStarted] = useState(false);

  const activeOrderIdRef = useRef<number | null>(selectedOrderId);
  const activeRunIdRef = useRef<number | null>(selectedRunId);
  activeOrderIdRef.current = selectedOrderId;
  activeRunIdRef.current = selectedRunId;

  const isActiveWorkflow = useCallback(
    (runId: number, orderId: number) =>
      activeOrderIdRef.current === orderId && activeRunIdRef.current === runId,
    [],
  );

  const patientHistory = usePatientHistory(nomorRm);
  const orderTestRuns = useOrderTestRuns(selectedOrderId);

  const activeHistory = activeHistoryFor(patientHistory.data, nomorRm);
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
    if (patientHistory.loading) {
      setPatientRequestStarted(true);
    }
  }, [patientHistory.loading]);

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
    // Only reconcile the order once history is loaded, so a seeded
    // initialOrderId is validated against real data rather than wiped against
    // the empty pre-load order list. Mirrors the visit effect's guard above.
    if (activeHistory === null) return;

    setSelectedOrderId((currentOrderId) => {
      if (sortedOrders.some((order) => order.id_order === currentOrderId)) {
        return currentOrderId;
      }

      return sortedOrders[0]?.id_order ?? null;
    });
  }, [activeHistory, sortedOrders]);

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

  const patientContent = !activeHistory && !patientRequestStarted ? (
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
        ) : activeTestRuns === null && !testRunRequestStarted ? (
          <LoadingState message="Loading test runs..." />
        ) : activeTestRuns === null && orderTestRuns.loading ? (
          <LoadingState message="Loading test runs..." />
        ) : activeTestRuns === null && orderTestRuns.error ? (
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
            {orderTestRuns.loading ? (
              <p role="status" style={{ color: "var(--color-text-secondary)" }}>
                Refreshing test runs...
              </p>
            ) : null}
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
            ) : (
              <>
                <FinalRunWorkflow
                  key={`${selectedOrderId}:${selectedTestRun.id_run}`}
                  disabled={orderTestRuns.loading}
                  isActive={isActiveWorkflow}
                  onRefetch={orderTestRuns.refetch}
                  selectedRun={selectedTestRun}
                />
                <SimrsSyncWorkflow
                  key={`${selectedOrderId}:${selectedTestRun.id_run}`}
                  disabled={orderTestRuns.loading}
                  isActive={isActiveWorkflow}
                  onRefetch={orderTestRuns.refetch}
                  selectedRun={selectedTestRun}
                />
                {selectedTestRun.results.length === 0 ? (
                  <EmptyState
                    title="No results found"
                    message="No results were found for this test run."
                  />
                ) : (
                  <ResultTable results={selectedTestRun.results} />
                )}
              </>
            )}
          </>
        ) : null
      ) : null}
    </>
  ) : null;

  return (
    <section
      aria-label="Order detail"
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
    >
      {onBack ? (
        <div>
          <button
            type="button"
            onClick={onBack}
            style={{
              background: "none",
              border: "1px solid var(--color-border)",
              borderRadius: "4px",
              color: "var(--color-primary)",
              cursor: "pointer",
              fontSize: "0.875rem",
              padding: "var(--space-1) var(--space-3)",
            }}
          >
            ← Back to worklist
          </button>
        </div>
      ) : null}
      {patientContent}
    </section>
  );
}
