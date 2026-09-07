import { useCallback, useEffect, useRef, useState } from "react"
import { getResults } from "../api/endpoints"
import type { PaginatedResultResponse } from "../types/api"
import type { ResultsQueryParams } from "../api/endpoints"

export interface UseResultsResult {
  data: PaginatedResultResponse | null
  loading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("Failed to load results")
}

export function useResults(
  params: ResultsQueryParams = {},
): UseResultsResult {
  const {
    page,
    page_size,
    nomor_rm,
    id_instrument,
    id_order,
    id_run,
    is_final,
    delivery_status,
    start_date,
    end_date,
  } = params
  const [data, setData] = useState<PaginatedResultResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const requestGeneration = useRef(0)

  const refetch = useCallback(async () => {
    const generation = requestGeneration.current + 1
    requestGeneration.current = generation
    setLoading(true)
    setError(null)

    try {
      const nextData = await getResults({
        page,
        page_size,
        nomor_rm,
        id_instrument,
        id_order,
        id_run,
        is_final,
        delivery_status,
        start_date,
        end_date,
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
  }, [
    page,
    page_size,
    nomor_rm,
    id_instrument,
    id_order,
    id_run,
    is_final,
    delivery_status,
    start_date,
    end_date,
  ])

  useEffect(() => {
    let active = true
    queueMicrotask(() => {
      if (!active) return

      setData(null)
      void refetch()
    })

    return () => {
      active = false
      requestGeneration.current += 1
    }
  }, [refetch])

  return { data, loading, error, refetch }
}
