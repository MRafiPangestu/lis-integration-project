import { apiClient } from "./client"
import type { SyncSimrsResponse, TestRunResponse } from "../types/api"

export function finalizeTestRun(runId: number): Promise<TestRunResponse> {
  return apiClient.post<TestRunResponse>(
    `/api/test-runs/${encodeURIComponent(String(runId))}/finalize`,
  )
}

export function unfinalizeTestRun(runId: number): Promise<TestRunResponse> {
  return apiClient.post<TestRunResponse>(
    `/api/test-runs/${encodeURIComponent(String(runId))}/unfinalize`,
  )
}

export function syncTestRunToSimrs(runId: number): Promise<SyncSimrsResponse> {
  return apiClient.post<SyncSimrsResponse>(
    `/api/test-runs/${encodeURIComponent(String(runId))}/sync-simrs`,
  )
}
