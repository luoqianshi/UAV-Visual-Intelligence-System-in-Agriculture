import client from './client'

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
  // 数据集管理
  fetchDatasets: (params?: { format?: string }) =>
    client.get<unknown, { data: { datasets: Dataset[]; total: number; format_dist: Record<string, number> } }>('/datasets', { params }),
  fetchDataset: (id: string) => client.get<unknown, { data: Dataset }>(`/datasets/${id}`),
  fetchDatasetReport: (id: string) => client.get<unknown, { data: any }>(`/datasets/${id}/report`),
}
