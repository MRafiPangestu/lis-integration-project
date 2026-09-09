import { ApiError } from "../../api/client";
import { FilterBar, type FilterBarProps } from "../layout/FilterBar";
import { EmptyState } from "../status/EmptyState";
import { ErrorState } from "../status/ErrorState";
import { LoadingState } from "../status/LoadingState";
import { useInstrumentOrders, OVERVIEW_PAGE_SIZE } from "../../hooks/useInstrumentOrders";
import type { OrderOverviewRow as OrderOverviewRowData } from "../../types/api";
import { ALL_DATE_FROM, ALL_DATE_TO } from "./dateRange";
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
  searchProps: FilterBarProps;
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
  searchProps,
}: OrderOverviewViewProps) {
  const orders = useInstrumentOrders(instrumentId, dateFrom, dateTo, page);
  const isAllRange = dateFrom === ALL_DATE_FROM && dateTo === ALL_DATE_TO;

  const openOrder = (row: OrderOverviewRowData) =>
    onOpenOrder({
      nomorRm: row.nomor_rm,
      idVisit: row.id_visit,
      idOrder: row.id_order,
    });

  const isNotFound = orders.error instanceof ApiError && orders.error.status === 404;

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
      <OrderOverviewTable
        rows={[]}
        onOpenOrder={openOrder}
        refreshing={orders.loading}
        emptyMessage={
          isAllRange
            ? "No orders recorded for this instrument."
            : `No orders for this instrument between ${dateFrom} and ${dateTo}.`
        }
      />
    );
  } else if (orders.data) {
    body = (
      <OrderOverviewTable
        rows={orders.data.items}
        onOpenOrder={openOrder}
        refreshing={orders.loading}
        footer={
          <Pagination
            page={orders.data.page}
            pageSize={OVERVIEW_PAGE_SIZE}
            total={orders.data.total}
            loading={orders.loading}
            onPageChange={onPageChange}
          />
        }
      />
    );
  }

  return (
    <section
      aria-label={`Order worklist for ${instrumentName}`}
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-3)",
        }}
      >
        <OverviewHeader total={orders.data?.total ?? null} loading={orders.loading} />
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
          }}
        >
          <div style={{ flex: "0 1 320px", minWidth: 200, display: "flex" }}>
            <FilterBar {...searchProps} />
          </div>
          <DateRangeFilter dateFrom={dateFrom} dateTo={dateTo} onChange={onDateChange} />
        </div>
      </div>
      {body}
    </section>
  );
}
