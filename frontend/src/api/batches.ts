import client from './client'

export interface Batch {
  batch_id: string
  batch_name: string
  crop_type: string
  flight_date: string
  plot_name?: string
  drone_model?: string
  flight_altitude_m?: number
  overlap_front?: number
  overlap_side?: number
  image_folder_path: string
  image_count: number
  total_size_bytes: number
  created_at: string
  image_formats: string[]
  status: string
  description?: string
}

export interface BatchSummary {
  total_batches: number
  total_images: number
  total_size_bytes: number
  resolutions: string[]
  formats: string[]
}

export interface BatchImage {
  filename: string
  size_bytes: number
  width: number
  height: number
  format: string
  thumbnail_url: string
  preview_url: string
}

export interface BatchListResponse {
  batches: Batch[]
  total: number
  summary: BatchSummary
}

export interface BatchImageListResponse {
  images: BatchImage[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ScanResult {
  valid: boolean
  image_count: number
  total_size_bytes: number
  formats: string[]
  message?: string
}

export interface CreateBatchResponse {
  batch_id: string
  image_count: number
  total_size_mb: number
}

export const batchesApi = {
  list: (params?: { crop_type?: string; flight_date?: string; plot_name?: string }) =>
    client.get<unknown, { data: BatchListResponse }>('/batches', { params }),

  get: (batchId: string) =>
    client.get<unknown, { data: Batch }>(`/batches/${batchId}`),

  create: (data: Partial<Batch> & { image_folder_path: string }) =>
    client.post<unknown, { data: CreateBatchResponse }>('/batches', data),

  update: (batchId: string, data: Partial<Batch>) =>
    client.put<unknown, { data: Batch }>(`/batches/${batchId}`, data),

  delete: (batchId: string) =>
    client.delete<unknown, any>(`/batches/${batchId}`),

  listImages: (batchId: string, params?: { page?: number; page_size?: number; sort_by?: string; order?: string }) =>
    client.get<unknown, { data: BatchImageListResponse }>(`/batches/${batchId}/images`, { params }),

  imagePreviewUrl: (batchId: string, filename: string, size: 'thumbnail' | 'medium' | 'original' = 'thumbnail') =>
    `/api/batches/${batchId}/images/${encodeURIComponent(filename)}/preview?size=${size}`,

  scanPath: (image_folder_path: string) =>
    client.post<unknown, { data: ScanResult }>('/batches/scan', { image_folder_path }),
}
