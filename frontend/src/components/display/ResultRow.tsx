import type { ResultResponse } from "../../types/api"
import { ResultFlag } from "./ResultFlag"

export interface ResultRowProps {
  result: ResultResponse
}

const clinicalCellStyle = {
  fontFamily: "var(--font-clinical)",
  padding: "var(--space-2)",
  textAlign: "left" as const,
  verticalAlign: "top" as const,
}

const textCellStyle = {
  padding: "var(--space-2)",
  textAlign: "left" as const,
  verticalAlign: "top" as const,
}

export function ResultRow({ result }: ResultRowProps) {
  return (
    <tr>
      <td style={clinicalCellStyle}>{result.parameter_tes}</td>
      <td style={clinicalCellStyle}>{result.nilai_hasil}</td>
      <td style={clinicalCellStyle}>{result.satuan ?? "—"}</td>
      <td style={clinicalCellStyle}>
        {result.reference_range_snapshot ?? "—"}
      </td>
      <td style={textCellStyle}>
        <ResultFlag flag={result.flag_abnormalitas} />
      </td>
    </tr>
  )
}
