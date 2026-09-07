import { useCallback, useEffect, useRef, useState } from "react"
import {
  finalizeTestRun,
  syncTestRunToSimrs,
  unfinalizeTestRun,
} from "../api/mutations"
import type { SyncSimrsResponse, TestRunResponse } from "../types/api"

export interface MutationState<T> {
  mutate: (runId: number) => Promise<T>
  loading: boolean
  error: Error | null
}

interface RunLockEntry {
  owner: symbol | null
  listeners: Set<() => void>
}

const runLocks = new Map<number, RunLockEntry>()

function getRunLock(runId: number): RunLockEntry {
  const existing = runLocks.get(runId)
  if (existing) return existing

  const created: RunLockEntry = { owner: null, listeners: new Set() }
  runLocks.set(runId, created)
  return created
}

function notifyRunLock(entry: RunLockEntry): void {
  entry.listeners.forEach((listener) => listener())
}

function cleanRunLock(runId: number, entry: RunLockEntry): void {
  if (entry.owner === null && entry.listeners.size === 0) {
    runLocks.delete(runId)
  }
}

export interface WorkflowMutationLock {
  locked: boolean
  acquire: () => boolean
  release: () => void
}

export function useWorkflowMutationLock(runId: number): WorkflowMutationLock {
  const ownerRef = useRef<symbol | null>(null)
  const [, forceUpdate] = useState(0)

  if (ownerRef.current === null) {
    ownerRef.current = Symbol("workflow-mutation")
  }

  useEffect(() => {
    const entry = getRunLock(runId)
    const listener = () => forceUpdate((current) => current + 1)
    entry.listeners.add(listener)

    return () => {
      entry.listeners.delete(listener)
      if (entry.owner === ownerRef.current) {
        entry.owner = null
        notifyRunLock(entry)
      }
      cleanRunLock(runId, entry)
    }
  }, [runId])

  const acquire = useCallback(() => {
    const entry = getRunLock(runId)
    if (entry.owner !== null && entry.owner !== ownerRef.current) return false

    entry.owner = ownerRef.current
    notifyRunLock(entry)
    return true
  }, [runId])

  const release = useCallback(() => {
    const entry = runLocks.get(runId)
    if (!entry || entry.owner !== ownerRef.current) return

    entry.owner = null
    notifyRunLock(entry)
    cleanRunLock(runId, entry)
  }, [runId])

  return {
    acquire,
    locked: getRunLock(runId).owner !== null,
    release,
  }
}

function toError(error: unknown, fallback: string): Error {
  return error instanceof Error ? error : new Error(fallback)
}

function useRunMutation<T>(
  mutation: (runId: number) => Promise<T>,
  fallbackError: string,
): MutationState<T> {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const mountedRef = useRef(true)
  const loadingRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const mutate = useCallback(async (runId: number): Promise<T> => {
    if (loadingRef.current) {
      throw new Error("A mutation is already in progress.")
    }

    loadingRef.current = true
    if (mountedRef.current) {
      setLoading(true)
      setError(null)
    }

    try {
      return await mutation(runId)
    } catch (mutationError) {
      const nextError = toError(mutationError, fallbackError)
      if (mountedRef.current) setError(nextError)
      throw nextError
    } finally {
      loadingRef.current = false
      if (mountedRef.current) setLoading(false)
    }
  }, [fallbackError, mutation])

  return { error, loading, mutate }
}

export function useFinalizeTestRun(): MutationState<TestRunResponse> {
  return useRunMutation(finalizeTestRun, "Unable to finalize the test run.")
}

export function useUnfinalizeTestRun(): MutationState<TestRunResponse> {
  return useRunMutation(unfinalizeTestRun, "Unable to unfinalize the test run.")
}

export function useSyncTestRunToSimrs(): MutationState<SyncSimrsResponse> {
  return useRunMutation(syncTestRunToSimrs, "Unable to synchronize the test run.")
}
