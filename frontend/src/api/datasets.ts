import client from './client'

export type DatasetFormat = 'YOLO' | 'COCO' | 'VOC'
export type DatasetSource = 'imported' | 'built'

export interface DatasetSplit { image_count: number; object_count: number }

export interface Dataset {
  dataset_id: string
  name: string
  format: DatasetFormat
  source: DatasetSource
  path: string
  classes: string[]
  splits: Record<'train' | 'val' | 'test', DatasetSplit>
  image_count: number
  object_count: number
  origin_image_count: number
  image_size: string
  version: string
  description: string
  created_at: string
  status: 'ready' | 'building' | 'failed'
  // 兼容旧模板的派生字段
  id: string
  sample_count: number
  train_count: number
  val_count: number
  test_count: number
}

export interface ScanResult {
  valid: boolean
  format: DatasetFormat | null
  classes: string[]
  image_count: number
  object_count: number
  splits: Record<string, DatasetSplit>
  origin_image_count: number
  image_size: string
  version: string
  description: string
  message: string
}

export interface DatasetReport {
  dataset_id: string
  summary: {
    total_images: number
    total_objects: number
    origin_image_count: number
    non_empty_images: number
    splits: Record<string, DatasetSplit>
  }
  class_dist: { name: string; class_id: number; count: number; pct: number }[]
  bbox_stats: {
    avg_width: number; avg_height: number
    area_hist: [number[], number][]
    size_dist: { small: number; medium: number; large: number }
  }
  image_stats: { resolutions: Record<string, number>; aspect_ratios: Record<string, number> }
  warnings: string[]
  cached: boolean
  generated_at: string
}

export interface DatasetImage {
  filename: string; split: string; size_bytes: number
  width: number; height: number; format: string
  thumbnail_url: string; preview_url: string
}

function normalize(d: any): Dataset {
  const s = d.splits || {}
  return {
    ...d,
    id: d.dataset_id,
    sample_count: d.image_count,
    train_count: s.train?.image_count || 0,
    val_count: s.val?.image_count || 0,
    test_count: s.test?.image_count || 0,
  }
}

export const datasetsApi = {
  fetchDatasets: (params?: { format?: string }) =>
    client.get<unknown, { data: { datasets: Dataset[]; total: number; format_dist: Record<string, number> } }>(
      '/datasets', { params }).then((res: any) => ({
        ...res,
        data: { ...res.data, datasets: (res.data.datasets || []).map(normalize) },
      })),
  fetchDataset: (id: string) =>
    client.get<unknown, { data: Dataset }>(`/datasets/${id}`).then((res: any) => ({
      ...res, data: normalize(res.data),
    })),
  scan: (path: string) =>
    client.post<unknown, { data: ScanResult }>('/datasets/scan', { path }),
  import: (path: string, name?: string, description?: string) =>
    client.post<unknown, { data: Dataset }>('/datasets/import', { path, name, description }),
  fetchReport: (id: string, force = false) =>
    client.get<unknown, { data: DatasetReport }>(`/datasets/${id}/report`, { params: { force } }),
  fetchImages: (id: string, params: { split?: string; page?: number; page_size?: number }) =>
    client.get<unknown, { data: { images: DatasetImage[]; total: number; page: number; page_size: number; total_pages: number; split: string } }>(
      `/datasets/${id}/images`, { params }),
  delete: (id: string, deleteFiles = false) =>
    client.delete<unknown, { data: null }>(`/datasets/${id}`, { params: { delete_files: deleteFiles } }),
  pickFolder: () => client.post<unknown, { data: { path?: string; cancelled?: boolean } }>('/datasets/pick-folder'),
}
