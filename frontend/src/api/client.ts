/** API client for the building energy analysis backend */
import axios from 'axios';
import type {
  ParsedData, AnalysisResult, CarbonResult, StandardInfo,
  FullPipelineResult,
} from '../types/analysis';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

// ---- Unified error handling ----

api.interceptors.response.use(
  (response) => response,
  (error) => {
    let msg = '请求失败';
    if (error.response?.data) {
      // FastAPI validation errors
      if (error.response.data.detail) {
        if (Array.isArray(error.response.data.detail)) {
          msg = error.response.data.detail
            .map((d: { msg: string; loc: string[] }) => `${d.loc.join('.')}: ${d.msg}`)
            .join('; ');
        } else if (typeof error.response.data.detail === 'string') {
          msg = error.response.data.detail;
        }
      } else if (typeof error.response.data === 'string') {
        msg = error.response.data;
      }
    } else if (error.code === 'ECONNABORTED') {
      msg = '请求超时，请检查网络后重试';
    } else if (!error.response) {
      msg = '无法连接到服务器，请确认后端已启动';
    }
    return Promise.reject(new Error(msg));
  }
);

// ---- Helper to extract error message for direct display ----

export function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  return '未知错误';
}

// ---- Upload ----

export async function uploadFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  });
  return data as { file_id: string; filename: string; size_bytes: number; preview: unknown };
}

// ---- Parse ----

export async function parseData(input: { file_id?: string; raw_text?: string; column_map?: Record<string, string>; daily?: boolean }) {
  const { data } = await api.post('/parse', input);
  return data as ParsedData;
}

// ---- Preview ----

export async function previewFile(fileId: string) {
  const { data } = await api.get(`/preview/${fileId}`);
  return data as {
    sheets: Array<{
      name: string; total_rows: number; total_cols: number;
      preview_rows: Array<{ row: number; cells: Record<string, string> }>;
      headers: Record<string, string>;
    }>;
    detection: { mode: string; confidence: number; suggestion: string; sheet?: string;
      data_start_row?: number; month_start_col?: number; num_month_cols?: number; };
  };
}

// ---- Transposed Parse ----

export async function parseTransposed(params: {
  file_id: string; sheet_name?: string; start_row?: number;
  month_start_col?: number; num_months?: number; year?: number;
}) {
  const { data } = await api.post('/parse/transposed', params);
  return data as ParsedData;
}

// ---- Analyze ----

export async function analyzeEnergy(params: {
  energy_data: unknown[];
  building_info: Record<string, unknown>;
  coal_factors_preset?: string;
}) {
  const { data } = await api.post('/analyze', params);
  return data as AnalysisResult;
}

// ---- Carbon ----

export async function calculateCarbon(params: {
  energy_data: unknown[];
  building_info: Record<string, unknown>;
  province?: string;
  building_type?: string;
  star_rating?: string;
  climate_zone?: string;
  standard_choice?: string;
}) {
  const { data } = await api.post('/carbon', params);
  return data as CarbonResult;
}

// ---- Full Pipeline ----

export async function fullPipeline(params: {
  file_id?: string;
  raw_text?: string;
  energy_data?: unknown[];
  column_map?: Record<string, string>;
  daily?: boolean;
  building_info?: Record<string, unknown>;
  coal_factors_preset?: string;
  province?: string;
  building_type?: string;
  star_rating?: string;
  climate_zone?: string;
  standard_choice?: string;
}) {
  const { data } = await api.post('/pipeline/full', params);
  return data as FullPipelineResult;
}

// ---- Report ----

export async function downloadReport(reportData: Record<string, unknown>) {
  const response = await api.post('/report', reportData, {
    responseType: 'blob',
    timeout: 180000,
  });
  return response.data as Blob;
}

// ---- Standards ----

export async function matchStandard(params: { building_type: string; province: string; city?: string }) {
  const { data } = await api.get('/standards/match', { params });
  return data as { matched: boolean; standard: StandardInfo | null; message?: string };
}

export async function listStandards() {
  const { data } = await api.get('/standards');
  return data as { standards: Array<Record<string, unknown>> };
}

export async function getGridFactors() {
  const { data } = await api.get('/factors/grid');
  return data as { factors: Array<Record<string, unknown>> };
}

// ---- Health ----

export async function healthCheck() {
  const { data } = await api.get('/health');
  return data;
}
