export type ApiErrorKind = "network" | "http" | "parse"

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | undefined

  constructor(
    message: string,
    kind: ApiErrorKind,
    status?: number,
  ) {
    super(message)
    this.name = "ApiError"
    this.kind = kind
    this.status = status
  }
}

const API_BASE_URL = "http://localhost:8000"

async function get<T>(path: string): Promise<T> {
  const url = new URL(path, `${API_BASE_URL}/`)

  let response: Response
  try {
    response = await fetch(url)
  } catch (error) {
    const detail = error instanceof Error ? `: ${error.message}` : ""
    throw new ApiError(
      `Network request failed for GET ${url.pathname}${detail}`,
      "network",
    )
  }

  if (!response.ok) {
    let detail = ""
    try {
      detail = (await response.text()).trim()
    } catch {
      detail = ""
    }

    const suffix = detail.length > 0 ? `: ${detail}` : ""
    throw new ApiError(
      `API request failed with ${response.status} ${response.statusText}${suffix}`,
      "http",
      response.status,
    )
  }

  let payload: unknown
  try {
    payload = JSON.parse(await response.text())
  } catch {
    throw new ApiError(
      `API response was not valid JSON for GET ${url.pathname}`,
      "parse",
      response.status,
    )
  }

  return payload as T
}

export const apiClient = {
  get,
}
