import { useCallback, useEffect, useRef, useState } from "react"
import { getInstrumentStatuses } from "../api/endpoints"
import type { InstrumentStatusResponse } from "../types/api"

export interface UseInstrumentsResult {
  data: InstrumentStatusResponse[] | null
  loading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("Failed to load instruments")
}

export function useInstruments(): UseInstrumentsResult {
  const [data, setData] = useState<InstrumentStatusResponse[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const requestGeneration = useRef(0)

  const refetch = useCallback(async () => {
    const generation = requestGeneration.current + 1
    requestGeneration.current = generation
    setLoading(true)
    setError(null)

    try {
      const nextData = await getInstrumentStatuses()
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
  }, [])

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
