import { ApiError } from "../../api/client"
import {
  useSyncTestRunToSimrs,
  useWorkflowMutationLock,
} from "../../hooks/useMutations"
import type { TestRunResponse } from "../../types/api"
import { useToast } from "./ToastProvider"

export interface SimrsSyncWorkflowProps {
  selectedRun: TestRunResponse
  onRefetch: () => Promise<void>
  isActive: (runId: number, orderId: number) => boolean
  disabled?: boolean
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "The selected test run no longer exists."
    if (error.status === 409) return "The test run cannot be synchronized in its current state."
  }

  return "SIMRS synchronization failed. Please try again."
}

export function SimrsSyncWorkflow({
  selectedRun,
  onRefetch,
  isActive,
  disabled = false,
}: SimrsSyncWorkflowProps) {
  const syncMutation = useSyncTestRunToSimrs()
  const workflowLock = useWorkflowMutationLock(selectedRun.id_run)
  const { showError, showSuccess } = useToast()
  const deliveryStatus = selectedRun.delivery_status.trim().toLowerCase()
  const mutationDisabled = disabled || syncMutation.loading || workflowLock.locked
  const canSync = selectedRun.is_final && (deliveryStatus === "pending" || deliveryStatus === "failed")

  const handleSync = async () => {
    const operation = {
      orderId: selectedRun.id_order,
      runId: selectedRun.id_run,
    }

    if (!workflowLock.acquire()) return

    try {
      const response = await syncMutation.mutate(operation.runId)
      if (!isActive(operation.runId, operation.orderId)) return

      const simrsError = response.simrs_error?.trim()

      if (!response.simrs_success || simrsError) {
        showError(simrsError || "SIMRS synchronization failed.")
        try {
          await onRefetch()
        } catch {
          if (isActive(operation.runId, operation.orderId)) {
            showError("SIMRS status changed, but the latest data could not be refreshed.")
          }
        }
        return
      }

      showSuccess("Test run synchronized to SIMRS successfully.")
      try {
        await onRefetch()
      } catch {
        if (isActive(operation.runId, operation.orderId)) {
          showError("SIMRS status changed, but the latest data could not be refreshed.")
        }
      }
    } catch (error) {
      if (isActive(operation.runId, operation.orderId)) {
        showError(errorMessage(error))
      }
    } finally {
      workflowLock.release()
    }
  }

  return (
    <section
      aria-labelledby="simrs-sync-workflow-title"
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-4)",
      }}
    >
      <h2 id="simrs-sync-workflow-title" style={{ fontSize: "1rem", marginBottom: "var(--space-2)" }}>
        SIMRS delivery
      </h2>
      <p style={{ marginBottom: "var(--space-3)" }}>
        Delivery status: <strong>{selectedRun.delivery_status || "Unknown"}</strong>
      </p>
      {!selectedRun.is_final ? (
        <p role="status" style={{ color: "var(--color-text-secondary)" }}>
          Finalize this test run before synchronizing it to SIMRS.
        </p>
      ) : canSync ? (
        <button className="lis-btn lis-btn--primary" disabled={mutationDisabled} onClick={() => void handleSync()} type="button">
          {syncMutation.loading
            ? "Synchronizing..."
            : deliveryStatus === "failed"
              ? "Retry SIMRS delivery"
              : "Sync to SIMRS"}
        </button>
      ) : (
        <p role="status" style={{ color: "var(--color-text-secondary)" }}>
          {deliveryStatus === "sending"
            ? "SIMRS delivery is sending."
            : deliveryStatus === "delivered"
              ? "SIMRS delivery is complete."
              : "No SIMRS action is available for this delivery status."}
        </p>
      )}
      {syncMutation.error ? (
        <p role="alert" style={{ color: "var(--color-flag-high)", marginTop: "var(--space-2)" }}>
          {errorMessage(syncMutation.error)}
        </p>
      ) : null}
    </section>
  )
}
