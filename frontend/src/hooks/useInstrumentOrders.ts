import { useCallback, useEffect, useRef, useState } from "react"
import { getInstrumentOrders } from "../api/endpoints"
import type { PaginatedOrderOverviewResponse } from "../types/api"

// M8.5 fixes the overview page size; the API accepts up to 100.
export const OVERVIEW_PAGE_SIZE = 25

export interface UseInstrumentOrdersResult {
  data: PaginatedOrderOverviewResponse | null
  loading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("Failed to load orders")
}

export function useInstrumentOrders(
  instrumentId: number | null,
  dateFrom: string,
  dateTo: string,
  page: number,
): UseInstrumentOrdersResult {
  const enabled = instrumentId !== null && dateFrom !== "" && dateTo !== ""
  const [data, setData] = useState<PaginatedOrderOverviewResponse | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<Error | null>(null)
  const requestGeneration = useRef(0)

  const refetch = useCallback(async () => {
    if (instrumentId === null || dateFrom === "" || dateTo === "") {
      requestGeneration.current += 1
      setData(null)
      setLoading(false)
      setError(null)
      return
    }

    const generation = requestGeneration.current + 1
    requestGeneration.current = generation
    setLoading(true)
    setError(null)

    try {
      const nextData = await getInstrumentOrders(instrumentId, {
        date_from: dateFrom,
        date_to: dateTo,
        page,
        page_size: OVERVIEW_PAGE_SIZE,
      })
      if (generation !== requestGeneration.current) return

      setData(nextData)
    } catch (requestError) {
      if (generation !== requestGeneration.current) return

      setError(toError(requestError))
    } finally {
      if (generation === requestGeneration.current) {
        setLoading(false)
      }
    }
  }, [instrumentId, dateFrom, dateTo, page])

  useEffect(() => {
    let active = true
    queueMicrotask(() => {
      if (active) void refetch()
    })

    return () => {
      active = false
      requestGeneration.current += 1
    }
  }, [refetch])

  return { data, loading, error, refetch }
}
