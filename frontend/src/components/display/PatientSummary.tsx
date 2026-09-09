import type {
  OrderResponse,
  PatientResponse,
  VisitResponse,
} from "../../types/api"

export interface PatientSummaryProps {
  patient: PatientResponse
  visit?: VisitResponse | null
  order?: OrderResponse | null
}

const emptyValue = "—"

function formatDate(value: string | null): string {
  if (!value) return emptyValue

  const parsed = new Date(value.length === 10 ? `${value}T00:00:00` : value)
  if (Number.isNaN(parsed.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(parsed)
}

function formatDateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed)
}

function displayValue(value: string | null | undefined): string {
  return value && value.trim().length > 0 ? value : emptyValue
}

const fieldGridStyle = {
  display: "grid",
  gap: "var(--space-3)",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
}

const fieldStyle = {
  display: "flex",
  flexDirection: "column" as const,
  gap: "var(--space-1)",
}

const labelStyle = {
  color: "var(--color-text-secondary)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "0.03em",
  textTransform: "uppercase" as const,
}

export function PatientSummary({
  patient,
  visit,
  order,
}: PatientSummaryProps) {
  const hasContext = visit !== null && visit !== undefined || order !== null && order !== undefined

  return (
    <section
      aria-labelledby="patient-summary-title"
      style={{
        backgroundColor: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-4)",
      }}
    >
      <h2
        id="patient-summary-title"
        style={{ fontSize: "1.125rem", marginBottom: "var(--space-4)" }}
      >
        Patient
      </h2>
      <div style={fieldGridStyle}>
        <div style={fieldStyle}>
          <span style={labelStyle}>Full Name</span>
          <span>{displayValue(patient.nama_lengkap)}</span>
        </div>
        <div style={fieldStyle}>
          <span style={labelStyle}>No. RM</span>
          <span style={{ fontFamily: "var(--font-clinical)" }}>
            {displayValue(patient.nomor_rm)}
          </span>
        </div>
        <div style={fieldStyle}>
          <span style={labelStyle}>Date of Birth</span>
          <span>{formatDate(patient.tanggal_lahir)}</span>
        </div>
        <div style={fieldStyle}>
          <span style={labelStyle}>Sex</span>
          <span>{displayValue(patient.jenis_kelamin)}</span>
        </div>
      </div>

      {hasContext ? (
        <section
          aria-labelledby="patient-summary-context-title"
          style={{
            borderTop: "1px solid var(--color-border)",
            marginTop: "var(--space-4)",
            paddingTop: "var(--space-4)",
          }}
        >
          <h3
            id="patient-summary-context-title"
            style={{ fontSize: "1rem", marginBottom: "var(--space-3)" }}
          >
            Visit and Order
          </h3>
          <div style={fieldGridStyle}>
            {visit ? (
              <div style={fieldStyle}>
                <span style={labelStyle}>Registration</span>
                <span style={{ fontFamily: "var(--font-clinical)" }}>
                  {displayValue(visit.no_registrasi)}
                </span>
              </div>
            ) : null}
            {order ? (
              <>
                <div style={fieldStyle}>
                  <span style={labelStyle}>Order</span>
                  <span style={{ fontFamily: "var(--font-clinical)" }}>
                    {order.id_order}
                  </span>
                </div>
                <div style={fieldStyle}>
                  <span style={labelStyle}>Unit</span>
                  <span>{order.id_unit ?? emptyValue}</span>
                </div>
                <div style={fieldStyle}>
                  <span style={labelStyle}>Doctor</span>
                  <span>{order.id_dokter ?? emptyValue}</span>
                </div>
                <div style={fieldStyle}>
                  <span style={labelStyle}>Order Time</span>
                  <span>{formatDateTime(order.waktu_order)}</span>
                </div>
                <div style={fieldStyle}>
                  <span style={labelStyle}>Diagnosis</span>
                  <span>{displayValue(order.diagnosa)}</span>
                </div>
              </>
            ) : null}
          </div>
        </section>
      ) : null}
    </section>
  )
}
