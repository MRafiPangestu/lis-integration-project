import { ApiError } from "../../api/client";
import { EmptyState } from "../status/EmptyState";
import { ErrorState } from "../status/ErrorState";
import { LoadingState } from "../status/LoadingState";
import { useInstrumentOrders, OVERVIEW_PAGE_SIZE } from "../../hooks/useInstrumentOrders";
import type { OrderOverviewRow as OrderOverviewRowData } from "../../types/api";
import { DateRangeFilter } from "./DateRangeFilter";
import { OverviewHeader } from "./OverviewHeader";
import { OrderOverviewTable } from "./OrderOverviewTable";
import { Pagination } from "./Pagination";

export interface OverviewDetailTarget {
  nomorRm: string;
  idVisit: number;
  idOrder: number;
}

export interface OrderOverviewViewProps {
  instrumentId: number;
  instrumentName: string;
  dateFrom: string;
  dateTo: string;
  page: number;
  onDateChange: (dateFrom: string, dateTo: string) => void;
  onPageChange: (page: number) => void;
  onOpenOrder: (target: OverviewDetailTarget) => void;
}

export function OrderOverviewView({
  instrumentId,
  instrumentName,
  dateFrom,
  dateTo,
  page,
  onDateChange,
  onPageChange,
  onOpenOrder,
}: OrderOverviewViewProps) {
  const orders = useInstrumentOrders(instrumentId, dateFrom, dateTo, page);

  const openOrder = (row: OrderOverviewRowData) =>
    onOpenOrder({
      nomorRm: row.nomor_rm,
      idVisit: row.id_visit,
      idOrder: row.id_order,
    });

  const isNotFound =
    orders.error instanceof ApiError && orders.error.status === 404;

  let body;
  if (orders.data === null && orders.loading) {
    body = <LoadingState message="Loading orders…" />;
  } else if (orders.data === null && isNotFound) {
    body = <EmptyState title="Instrument not found" message="This instrument is not available." />;
  } else if (orders.data === null && orders.error) {
    body = (
      <ErrorState
        error={orders.error}
        message="Unable to load the order worklist. Please try again."
        onRetry={orders.refetch}
        title="Worklist unavailable"
      />
    );
  } else if (orders.data && orders.data.total === 0) {
    body = (
      <EmptyState
        title="No orders"
        message={`No orders for this instrument between ${dateFrom} and ${dateTo}.`}
      />
    );
  } else if (orders.data) {
    body = (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-3)",
          opacity: orders.loading ? 0.6 : 1,
        }}
      >
        {orders.loading ? (
          <p role="status" style={{ color: "var(--color-text-secondary)", fontSize: "0.85rem" }}>
            Refreshing…
          </p>
        ) : null}
        <OrderOverviewTable rows={orders.data.items} onOpenOrder={openOrder} />
        <Pagination
          page={orders.data.page}
          pageSize={OVERVIEW_PAGE_SIZE}
          total={orders.data.total}
          loading={orders.loading}
          onPageChange={onPageChange}
        />
      </div>
    );
  }

  return (
    <section
      aria-label="Order worklist"
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
    >
      <OverviewHeader
        instrumentName={instrumentName}
        total={orders.data?.total ?? null}
        loading={orders.loading}
      />
      <DateRangeFilter dateFrom={dateFrom} dateTo={dateTo} onChange={onDateChange} />
      {body}
    </section>
  );
}
