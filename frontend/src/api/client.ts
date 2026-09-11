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

// Configurable so a deployed frontend can reach a non-localhost API — the
// dev value is the default (M9.1a design §9's coupled client.ts change).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

// The one fetch chokepoint (see M9.1a design §12.2) also owns the Bearer
// token: every request attaches it when present, and a 401 response clears
// it and notifies whoever is listening (AuthProvider) so the UI falls back
// to the login view. No token value is ever logged.
let authToken: string | null = null
let onUnauthorized: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(path, `${API_BASE_URL}/`)
  const method = init?.method ?? "GET"

  const headers = new Headers(init?.headers)
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`)
  }

  let response: Response
  try {
    response = await fetch(url, { ...init, headers })
  } catch (error) {
    const detail = error instanceof Error ? `: ${error.message}` : ""
    throw new ApiError(
      `Network request failed for ${method} ${url.pathname}${detail}`,
      "network",
    )
  }

  if (!response.ok) {
    if (response.status === 401) {
      authToken = null
      onUnauthorized?.()
    }

    let detail = ""
    try {
      detail = (await response.text()).trim()
    } catch {
      detail = ""
    }

    const suffix = detail.length > 0 ? `: ${detail}` : ""
    const requestContext = method === "GET" ? "" : ` for ${method} ${url.pathname}`
    throw new ApiError(
      `API request failed with ${response.status} ${response.statusText}${requestContext}${suffix}`,
      "http",
      response.status,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  let payload: unknown
  try {
    payload = JSON.parse(await response.text())
  } catch {
    throw new ApiError(
      `API response was not valid JSON for ${method} ${url.pathname}`,
      "parse",
      response.status,
    )
  }

  return payload as T
}

async function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  if (body === undefined) {
    return request<T>(path, { method: "POST" })
  }
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
}

export const apiClient = {
  get,
  post,
}
