export interface ResultResponse {
  id_hasil: number
  parameter_tes: string
  nilai_hasil: string
  satuan: string | null
  flag_abnormalitas: string | null
  reference_range_snapshot: string | null
  waktu_hasil: string
}

export interface TestRunResponse {
  id_run: number
  id_order: number
  id_instrument: number
  run_sequence: number
  waktu_run: string | null
  is_final: boolean
  delivery_status: string
  delivered_at: string | null
  created_at: string
  results: ResultResponse[]
}

export interface SyncSimrsResponse {
  run_id: number
  delivery_status: string
  delivered_at: string | null
  simrs_success: boolean
  simrs_status_code: number | null
  simrs_error: string | null
}

export interface PatientResponse {
  id_pasien: number
  nomor_rm: string
  nama_lengkap: string
  tanggal_lahir: string | null
  jenis_kelamin: string | null
}

export interface VisitResponse {
  id_visit: number
  id_pasien: number
  no_registrasi: string
  waktu_kunjungan: string
  created_at: string
}

export interface OrderResponse {
  id_order: number
  id_visit: number
  id_unit: number | null
  id_dokter: number | null
  diagnosa: string | null
  waktu_order: string
  status_order: string
}

export interface InstrumentResponse {
  id_instrument: number
  nama_mesin: string
  protokol: string | null
  tipe_koneksi: string | null
}

export interface InstrumentStatusResponse extends InstrumentResponse {
  connection_status: string
  last_status_at: string | null
}

export type HistoryResultResponse = ResultResponse

export interface HistoryTestRunResponse extends TestRunResponse {
  instrument: InstrumentResponse | null
  results: HistoryResultResponse[]
}

export interface HistoryOrderResponse extends OrderResponse {
  test_runs: HistoryTestRunResponse[]
}

export interface HistoryVisitResponse extends VisitResponse {
  orders: HistoryOrderResponse[]
}

export interface HistoryPatientResponse extends PatientResponse {
  visits: HistoryVisitResponse[]
}

export interface FlatResultResponse extends ResultResponse {
  test_run: TestRunResponse
  instrument: InstrumentResponse | null
  order: OrderResponse
  visit: VisitResponse
  patient: PatientResponse
}

export interface PaginatedResultResponse {
  items: FlatResultResponse[]
  page: number
  page_size: number
  total: number
}

// M8.4 instrument-scoped order overview — mirrors app/schemas/overview.py exactly.
export interface OrderOverviewRow {
  id_order: number
  waktu_order: string
  status_order: string
  nomor_rm: string
  nama_lengkap: string
  no_registrasi: string
  id_visit: number
  effective_run_id: number | null
  effective_run_sequence: number | null
  effective_run_waktu_run: string | null
  is_final: boolean
  delivery_status: string | null
  delivered_at: string | null
  abnormal_count: number
}

export interface PaginatedOrderOverviewResponse {
  items: OrderOverviewRow[]
  page: number
  page_size: number
  total: number
}

// M9.1a — mirrors app/schemas/auth.py exactly. Never carries password_hash.
export type UserRole = "ANALYST" | "ADMIN"

export interface UserPublic {
  id_user: number
  username: string
  nama_lengkap: string
  role: UserRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserPublic
}
