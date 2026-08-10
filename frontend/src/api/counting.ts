import client from './client'

export interface CountingParams {
  tile_size?: number
  overlap_ratio?: number
  nms_iou?: number
  global_conf?: number
  batch_size?: number
  ground_resolution?: number
  grid_n?: number
  conf?: number
  iou?: number
  max_det?: number
  imgsz?: number
}

export interface TileResult {
  tile_index: number
  offset_x: number
  offset_y: number
  det_count: number
  max_det_reached: boolean
}

export interface CountingReport {
  count: number
  density_per_m2: number
  area_m2: number
  heatmap: number[][]
  confidence_dist: { high: number; mid: number; low: number }
  detection_data: any[]
  annotated_image: string
  model_info: { name: string; display_name: string; imgsz: number }
  params_snapshot: CountingParams
  image_size: [number, number]
  tile_count: number
  tile_results?: TileResult[]
  max_det_reached_tiles?: number[]
  filtered_count?: number
  result_id?: string
  created_at?: string
}

export interface CountingTaskStatus {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  result: any
  error: string | null
}

export const countingApi = {
  submit: (payload: { image_path?: string; image_dir?: string; model_name?: string } & CountingParams) =>
    client.post<unknown, { data: { task_id: string } }>('/counting', payload),
  submitWithFile: (file: File, model_name?: string, params?: CountingParams) => {
    const formData = new FormData()
    formData.append('image', file)
    if (model_name) formData.append('model_name', model_name)
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) formData.append(k, String(v))
      })
    }
    return client.post<unknown, { data: { task_id: string } }>('/counting', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getTask: (task_id: string) => client.get<unknown, { data: CountingTaskStatus }>(`/counting/tasks/${task_id}`),
  getResult: (task_id: string) => client.get<unknown, { data: CountingReport }>(`/counting/tasks/${task_id}/result`),
  history: () => client.get<unknown, { data: any[] }>('/counting/history'),
}
