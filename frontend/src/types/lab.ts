// src/types/lab.ts

export interface LabResult {
  nomor_rm: string;
  nama_lengkap: string;
  waktu_order: string;
  parameter_tes: string;
  nilai_hasil: string;
  satuan: string;
  flag_abnormalitas: string | null;
  status_hasil: string;
  reference_range_snapshot: string | null;
}