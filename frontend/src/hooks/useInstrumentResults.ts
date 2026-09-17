import { useCallback, useEffect, useRef, useState } from "react"
import { getInstrumentResults } from "../api/endpoints"
import type { PaginatedInstrumentResultSetResponse } from "../types/api"

// XN-550 unlinked instrument results list (G2). The API accepts up to 100.
export const INSTRUMENT_RESULTS_PAGE_SIZE = 25

export interface UseInstrumentResultsResult {
  data: PaginatedInstrumentResultSetResponse | null
  loading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("Failed to load instrument results")
}

export function useInstrumentResults(
  instrumentId: number | null,
  receivedFrom: string,
  receivedTo: string,
  page: number,
): UseInstrumentResultsResult {
  const enabled = instrumentId !== null && receivedFrom !== "" && receivedTo !== ""
  const [data, setData] = useState<PaginatedInstrumentResultSetResponse | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<Error | null>(null)
  const requestGeneration = useRef(0)

  const refetch = useCallback(async () => {
    if (instrumentId === null || receivedFrom === "" || receivedTo === "") {
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
      const nextData = await getInstrumentResults({
        received_from: receivedFrom,
        received_to: receivedTo,
        id_instrument: instrumentId,
        page,
        page_size: INSTRUMENT_RESULTS_PAGE_SIZE,
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
  }, [instrumentId, receivedFrom, receivedTo, page])

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
