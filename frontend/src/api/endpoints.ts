import { apiClient } from "./client"
import type {
  HistoryPatientResponse,
  InstrumentStatusResponse,
  LoginResponse,
  PaginatedOrderOverviewResponse,
  PaginatedResultResponse,
  TestRunResponse,
} from "../types/api"

export function login(username: string, password: string): Promise<LoginResponse> {
  return apiClient.post<LoginResponse>("/api/auth/login", { username, password })
}

export interface ResultsQueryParams {
  page?: number
  page_size?: number
  nomor_rm?: string
  id_instrument?: number
  id_order?: number
  id_run?: number
  is_final?: boolean
  delivery_status?: string
  start_date?: string
  end_date?: string
}

export function getOrderTestRuns(orderId: number): Promise<TestRunResponse[]> {
  const path = `/api/orders/${encodeURIComponent(String(orderId))}/test-runs`
  return apiClient.get<TestRunResponse[]>(path)
}

export function getResults(
  params: ResultsQueryParams = {},
): Promise<PaginatedResultResponse> {
  const searchParams = new URLSearchParams()

  if (params.page !== undefined) searchParams.set("page", String(params.page))
  if (params.page_size !== undefined) {
    searchParams.set("page_size", String(params.page_size))
  }
  if (params.nomor_rm !== undefined) searchParams.set("nomor_rm", params.nomor_rm)
  if (params.id_instrument !== undefined) {
    searchParams.set("id_instrument", String(params.id_instrument))
  }
  if (params.id_order !== undefined) {
    searchParams.set("id_order", String(params.id_order))
  }
  if (params.id_run !== undefined) searchParams.set("id_run", String(params.id_run))
  if (params.is_final !== undefined) {
    searchParams.set("is_final", String(params.is_final))
  }
  if (params.delivery_status !== undefined) {
    searchParams.set("delivery_status", params.delivery_status)
  }
  if (params.start_date !== undefined) {
    searchParams.set("start_date", params.start_date)
  }
  if (params.end_date !== undefined) searchParams.set("end_date", params.end_date)

  const query = searchParams.toString()
  const path = query.length > 0 ? `/api/results?${query}` : "/api/results"
  return apiClient.get<PaginatedResultResponse>(path)
}

export function getPatientHistory(nomorRm: string): Promise<HistoryPatientResponse> {
  const path = `/api/patients/${encodeURIComponent(nomorRm)}/history`
  return apiClient.get<HistoryPatientResponse>(path)
}

export function getInstrumentStatuses(): Promise<InstrumentStatusResponse[]> {
  return apiClient.get<InstrumentStatusResponse[]>("/api/instruments/status")
}

export interface InstrumentOrdersQueryParams {
  date_from: string
  date_to: string
  page: number
  page_size: number
}

export function getInstrumentOrders(
  instrumentId: number,
  params: InstrumentOrdersQueryParams,
): Promise<PaginatedOrderOverviewResponse> {
  const searchParams = new URLSearchParams()
  // Both bounds are server-local naive timestamps: send the datetime-local
  // string verbatim (no toISOString, no Z, no offset).
  searchParams.set("date_from", params.date_from)
  searchParams.set("date_to", params.date_to)
  searchParams.set("page", String(params.page))
  searchParams.set("page_size", String(params.page_size))

  const path = `/api/instruments/${encodeURIComponent(String(instrumentId))}/orders?${searchParams.toString()}`
  return apiClient.get<PaginatedOrderOverviewResponse>(path)
}
