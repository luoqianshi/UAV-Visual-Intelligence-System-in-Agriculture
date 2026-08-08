import client from './client'

export interface Batch {
  id: string
  name: string
  crop_type: string
  flight_date: string
  location: string
  drone_model: string
  altitude_m: number
  image_count: number
  resolution: string
  status: string
  created_at: string
  description?: string
  plot_id?: string
  sensor?: string
}

export interface ProcessingTask {
  id: string
  name: string
  type: 'clahe' | 'crop'
  batch_id: string
  status: 'processing' | 'completed' | 'failed'
  progress: number
  input_path: string
  output_path: string
  params: Record<string, any>
  total_images: number
  processed_images: number
  created_at: string
  completed_at?: string
  error?: string
}

export interface Dataset {
  id: string
  name: string
  version: string
  format: 'YOLO' | 'COCO' | 'VOC'
  crop_type: string
  sample_count: number
  train_count: number
  val_count: number
  test_count: number
  classes: string[]
  created_at: string
  status: string
  size_mb: number
  path: string
  description?: string
}

export const mockApi = {
  // 数据管理
  fetchBatches: (params?: { crop_type?: string; status?: string }) =>
    client.get<unknown, { data: { batches: Batch[]; total: number } }>('/batches', { params }),
  createBatch: (body: Partial<Batch>) => client.post<unknown, any>('/batches', body),
  fetchBatch: (id: string) => client.get<unknown, { data: Batch }>(`/batches/${id}`),
  fetchBatchImages: (id: string) =>
    client.get<unknown, { data: { images: any[]; total: number } }>(`/batches/${id}/images`),
  batchImagePreviewUrl: (batchId: string, file: string) =>
    `/api/batches/${batchId}/images/${file}/preview`,

  // 数据处理
  fetchTasks: (params?: { type?: string; status?: string }) =>
    client.get<unknown, { data: { tasks: ProcessingTask[]; total: number } }>('/processing/tasks', { params }),
  fetchTask: (id: string) => client.get<unknown, { data: ProcessingTask }>(`/processing/tasks/${id}`),
  taskPreviewUrl: (taskId: string, type?: 'original' | 'result') =>
    `/api/processing/tasks/${taskId}/preview${type ? `?type=${type}` : ''}`,

  // 数据集管理
  fetchDatasets: (params?: { format?: string }) =>
    client.get<unknown, { data: { datasets: Dataset[]; total: number; format_dist: Record<string, number> } }>('/datasets', { params }),
  fetchDataset: (id: string) => client.get<unknown, { data: Dataset }>(`/datasets/${id}`),
  fetchDatasetReport: (id: string) => client.get<unknown, { data: any }>(`/datasets/${id}/report`),
}
