import type { HistoryOrderResponse, HistoryVisitResponse } from "../../types/api"

export interface VisitOrderSelectorProps {
  visits: HistoryVisitResponse[]
  selectedVisitId: number | null
  selectedOrderId: number | null
  onVisitSelect: (visitId: number) => void
  onOrderSelect: (orderId: number) => void
  disabled?: boolean
}

function timestamp(value: string | null | undefined): number | null {
  if (!value) return null

  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : parsed
}

function compareNewest(
  firstTime: string | null | undefined,
  firstId: number,
  secondTime: string | null | undefined,
  secondId: number,
): number {
  const firstTimestamp = timestamp(firstTime)
  const secondTimestamp = timestamp(secondTime)

  if (firstTimestamp !== null || secondTimestamp !== null) {
    if (firstTimestamp === null) return 1
    if (secondTimestamp === null) return -1
    if (firstTimestamp !== secondTimestamp) {
      return secondTimestamp - firstTimestamp
    }
  }

  return secondId - firstId
}

function sortVisits(visits: HistoryVisitResponse[]): HistoryVisitResponse[] {
  return [...visits].sort((first, second) =>
    compareNewest(
      first.waktu_kunjungan,
      first.id_visit,
      second.waktu_kunjungan,
      second.id_visit,
    ),
  )
}

function sortOrders(orders: HistoryOrderResponse[]): HistoryOrderResponse[] {
  return [...orders].sort((first, second) =>
    compareNewest(first.waktu_order, first.id_order, second.waktu_order, second.id_order),
  )
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed)
}

function orderLabel(order: HistoryOrderResponse): string {
  const diagnosis = order.diagnosa?.trim()
  const context = diagnosis ? ` — ${diagnosis}` : ""
  return `Order ${order.id_order} · ${formatDateTime(order.waktu_order)}${context}`
}

export function VisitOrderSelector({
  visits,
  selectedVisitId,
  selectedOrderId,
  onVisitSelect,
  onOrderSelect,
  disabled = false,
}: VisitOrderSelectorProps) {
  const sortedVisits = sortVisits(visits)
  const selectedVisit = sortedVisits.find((visit) => visit.id_visit === selectedVisitId)
  const sortedOrders = selectedVisit ? sortOrders(selectedVisit.orders) : []

  return (
    <section
      aria-labelledby="visit-order-selector-title"
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "4px",
        display: "grid",
        gap: "var(--space-3)",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
        padding: "var(--space-4)",
      }}
    >
      <h2 id="visit-order-selector-title" style={{ fontSize: "1rem", gridColumn: "1 / -1" }}>
        Visit and Order
      </h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label htmlFor="visit-selector" style={{ fontSize: "0.875rem", fontWeight: 600 }}>
          Visit
        </label>
        <select
          disabled={disabled || sortedVisits.length === 0}
          id="visit-selector"
          onChange={(event) => onVisitSelect(Number(event.target.value))}
          value={selectedVisitId ?? ""}
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: "4px",
            color: "var(--color-text-primary)",
            padding: "var(--space-2)",
          }}
        >
          <option disabled value="">
            Select a visit
          </option>
          {sortedVisits.map((visit) => (
            <option key={visit.id_visit} value={visit.id_visit}>
              {visit.no_registrasi} · {formatDateTime(visit.waktu_kunjungan)}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label htmlFor="order-selector" style={{ fontSize: "0.875rem", fontWeight: 600 }}>
          Order
        </label>
        <select
          disabled={disabled || sortedOrders.length === 0}
          id="order-selector"
          onChange={(event) => onOrderSelect(Number(event.target.value))}
          value={selectedOrderId ?? ""}
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: "4px",
            color: "var(--color-text-primary)",
            padding: "var(--space-2)",
          }}
        >
          <option disabled value="">
            {selectedVisit ? "Select an order" : "Select a visit first"}
          </option>
          {sortedOrders.map((order) => (
            <option key={order.id_order} value={order.id_order}>
              {orderLabel(order)}
            </option>
          ))}
        </select>
      </div>
    </section>
  )
}
