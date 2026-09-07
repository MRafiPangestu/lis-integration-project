import { useCallback, useEffect, useRef, useState } from "react"
import { getOrderTestRuns } from "../api/endpoints"
import type { TestRunResponse } from "../types/api"

export interface UseOrderTestRunsResult {
  data: TestRunResponse[] | null
  loading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error("Failed to load order test runs")
}

export function useOrderTestRuns(
  orderId: number | null | undefined,
): UseOrderTestRunsResult {
  const validOrderId =
    typeof orderId === "number" &&
    Number.isFinite(orderId) &&
    Number.isInteger(orderId) &&
    orderId > 0
      ? orderId
      : null
  const [data, setData] = useState<TestRunResponse[] | null>(null)
  const [loading, setLoading] = useState(validOrderId !== null)
  const [error, setError] = useState<Error | null>(null)
  const requestGeneration = useRef(0)

  const refetch = useCallback(async () => {
    if (validOrderId === null) {
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
      const nextData = await getOrderTestRuns(validOrderId)
      if (generation !== requestGeneration.current) return

      setData(nextData)
    } catch (requestError) {
      if (generation !== requestGeneration.current) return

      const nextError = toError(requestError)
      setError(nextError)
      throw nextError
    } finally {
      if (generation === requestGeneration.current) {
        setLoading(false)
      }
    }
  }, [validOrderId])

  useEffect(() => {
    let active = true
    queueMicrotask(() => {
      if (!active) return

      if (validOrderId === null) {
        void refetch().catch(() => undefined)
      } else {
        setData(null)
        void refetch().catch(() => undefined)
      }
    })

    return () => {
      active = false
      requestGeneration.current += 1
    }
  }, [refetch, validOrderId])

  return { data, loading, error, refetch }
}
