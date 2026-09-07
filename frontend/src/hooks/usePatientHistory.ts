import { useCallback, useEffect, useRef, useState } from "react"
import { getPatientHistory } from "../api/endpoints"
import type { HistoryPatientResponse } from "../types/api"

export interface UsePatientHistoryResult {
  data: HistoryPatientResponse | null
  loading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("Failed to load patient history")
}

export function usePatientHistory(
  nomorRm: string | null | undefined,
): UsePatientHistoryResult {
  const normalizedNomorRm = typeof nomorRm === "string" ? nomorRm.trim() : ""
  const hasValidIdentifier = normalizedNomorRm.length > 0
  const [data, setData] = useState<HistoryPatientResponse | null>(null)
  const [loading, setLoading] = useState(hasValidIdentifier)
  const [error, setError] = useState<Error | null>(null)
  const requestGeneration = useRef(0)

  const refetch = useCallback(async () => {
    if (!hasValidIdentifier) {
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
      const nextData = await getPatientHistory(normalizedNomorRm)
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
  }, [hasValidIdentifier, normalizedNomorRm])

  useEffect(() => {
    let active = true
    queueMicrotask(() => {
      if (!active) return

      if (!hasValidIdentifier) {
        void refetch()
      } else {
        setData(null)
        void refetch()
      }
    })

    return () => {
      active = false
      requestGeneration.current += 1
    }
  }, [hasValidIdentifier, refetch])

  return { data, loading, error, refetch }
}
