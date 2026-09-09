import { useEffect, useState } from "react"
import { ApiError } from "../../api/client"
import {
  useFinalizeTestRun,
  useUnfinalizeTestRun,
  useWorkflowMutationLock,
} from "../../hooks/useMutations"
import type { TestRunResponse } from "../../types/api"
import { ConfirmationDialog } from "./ConfirmationDialog"
import { useToast } from "./ToastProvider"

export interface FinalRunWorkflowProps {
  selectedRun: TestRunResponse
  onRefetch: () => Promise<void>
  isActive: (runId: number, orderId: number) => boolean
  disabled?: boolean
}

type PendingAction = "finalize" | "unfinalize" | null

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "The selected test run no longer exists."
    if (error.status === 409) return "The test run cannot be changed in its current state."
  }

  return fallback
}

export function FinalRunWorkflow({
  selectedRun,
  onRefetch,
  isActive,
  disabled = false,
}: FinalRunWorkflowProps) {
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const finalizeMutation = useFinalizeTestRun()
  const unfinalizeMutation = useUnfinalizeTestRun()
  const workflowLock = useWorkflowMutationLock(selectedRun.id_run)
  const { showError, showSuccess } = useToast()
  const mutationLoading = finalizeMutation.loading || unfinalizeMutation.loading

  useEffect(() => {
    setPendingAction(null)
  }, [selectedRun.id_run])

  const handleConfirm = async () => {
    if (!pendingAction) return

    const operation = {
      action: pendingAction,
      orderId: selectedRun.id_order,
      runId: selectedRun.id_run,
    }

    if (!workflowLock.acquire()) return

    try {
      if (operation.action === "finalize") {
        await finalizeMutation.mutate(operation.runId)
      } else {
        await unfinalizeMutation.mutate(operation.runId)
      }

      if (!isActive(operation.runId, operation.orderId)) return

      showSuccess(
        operation.action === "finalize"
          ? "Test run finalized successfully."
          : "Test run unfinalized successfully.",
      )
      setPendingAction(null)

      try {
        await onRefetch()
      } catch {
        if (isActive(operation.runId, operation.orderId)) {
          showError("The test run changed, but the latest data could not be refreshed.")
        }
      }
    } catch (error) {
      if (isActive(operation.runId, operation.orderId)) {
        showError(errorMessage(error, "The test run could not be updated."))
      }
    } finally {
      workflowLock.release()
    }
  }

  const deliveryStatus = selectedRun.delivery_status.trim().toLowerCase()
  const canUnfinalize = deliveryStatus === "pending" || deliveryStatus === "failed"
  const workflowDisabled = disabled || mutationLoading || workflowLock.locked
  const dialogLoading = mutationLoading || workflowLock.locked
  const mutationError = finalizeMutation.error ?? unfinalizeMutation.error

  return (
    <section
      aria-labelledby="final-run-workflow-title"
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-4)",
      }}
    >
      <h2 id="final-run-workflow-title" style={{ fontSize: "1rem", marginBottom: "var(--space-2)" }}>
        Clinical validation
      </h2>
      {selectedRun.is_final ? (
        <>
          <p style={{ color: "var(--color-text-secondary)", marginBottom: "var(--space-3)" }}>
            This test run is final.
          </p>
          {canUnfinalize ? (
            <button
              className="lis-btn lis-btn--secondary"
              disabled={workflowDisabled}
              onClick={() => setPendingAction("unfinalize")}
              type="button"
            >
              Unfinalize
            </button>
          ) : (
            <p role="status" style={{ color: "var(--color-text-secondary)" }}>
              Unfinalize is unavailable while delivery status is “{selectedRun.delivery_status}”.
            </p>
          )}
        </>
      ) : (
        <button
          className="lis-btn lis-btn--primary"
          disabled={workflowDisabled}
          onClick={() => setPendingAction("finalize")}
          type="button"
        >
          Finalize test run
        </button>
      )}
      {mutationError ? (
        <p role="alert" style={{ color: "var(--color-flag-high)", marginTop: "var(--space-2)" }}>
          {errorMessage(mutationError, "The test run could not be updated.")}
        </p>
      ) : null}
      <ConfirmationDialog
        cancelLabel="Cancel"
        confirmLabel={pendingAction === "unfinalize" ? "Unfinalize" : "Finalize"}
        loading={dialogLoading}
        message={
          pendingAction === "unfinalize"
            ? "Unfinalize this test run? It will no longer be marked as final."
            : "Finalize this test run? This confirms the selected clinical run."
        }
        onCancel={() => {
          if (!dialogLoading) setPendingAction(null)
        }}
        onConfirm={handleConfirm}
        open={pendingAction !== null}
        title={pendingAction === "unfinalize" ? "Confirm unfinalize" : "Confirm finalize"}
      />
    </section>
  )
}
