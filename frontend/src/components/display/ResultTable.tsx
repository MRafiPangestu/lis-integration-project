import type { ResultResponse } from "../../types/api"
import { ResultRow } from "./ResultRow"

export interface ResultTableProps {
  results: ResultResponse[]
}

const headerStyle = {
  backgroundColor: "var(--color-surface-hover)",
  borderBottom: "1px solid var(--color-border)",
  fontWeight: 600,
  padding: "var(--space-2)",
  textAlign: "left" as const,
}

export function ResultTable({ results }: ResultTableProps) {
  return (
    <div style={{ overflowX: "auto", width: "100%" }}>
      <table
        style={{
          backgroundColor: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderCollapse: "collapse",
          minWidth: "680px",
          width: "100%",
        }}
      >
        <caption
          style={{
            fontSize: "1rem",
            fontWeight: 600,
            padding: "var(--space-3)",
            textAlign: "left",
          }}
        >
          Laboratory results
        </caption>
        <thead>
          <tr>
            <th scope="col" style={headerStyle}>
              Parameter
            </th>
            <th scope="col" style={headerStyle}>
              Result
            </th>
            <th scope="col" style={headerStyle}>
              Unit
            </th>
            <th scope="col" style={headerStyle}>
              Reference Range
            </th>
            <th scope="col" style={headerStyle}>
              Flag
            </th>
          </tr>
        </thead>
        <tbody>
          {results.length > 0 ? (
            results.map((result) => (
              <ResultRow key={result.id_hasil} result={result} />
            ))
          ) : (
            <tr>
              <td
                colSpan={5}
                style={{
                  color: "var(--color-text-secondary)",
                  padding: "var(--space-6)",
                  textAlign: "center",
                }}
              >
                No laboratory results found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
