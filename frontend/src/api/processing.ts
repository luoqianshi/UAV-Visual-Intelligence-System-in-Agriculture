import client from './client'

export interface ProcessingTask {
  task_id: string
  name: string
  task_type: 'clahe' | 'crop'
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'interrupted'
  progress: number
  input_paths: string[]
  output_path: string
  params: {
    clip_limit?: number
    grid_size?: [number, number]
    tile_size?: number
    overlap_ratio?: number
  }
  total_images: number
  processed_images: number
  total_tiles: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
  sub_dirs: { sub_dir: string; image_count: number; tiles_count?: number }[]
}

export interface ProcessedItem {
  output_path: string
  task_id: string
  task_type: 'clahe' | 'crop'
  name: string
  status: string
  params: Record<string, any>
  image_count: number
  total_tiles: number
  created_at: string
  sub_dirs: { sub_dir: string; image_count: number; tiles_count?: number }[]
  has_task: boolean
}

export interface TaskFile {
  filename: string
  size_bytes: number
  width: number
  height: number
  format: string
  thumbnail_url: string
  preview_url: string
}

export interface TaskFileList {
  files: TaskFile[]
  total: number
  page: number
  page_size: number
  total_pages: number
  sub_dir: string
}

export interface TaskListResponse {
  tasks: ProcessingTask[]
  total: number
}

export interface ProcessedListResponse {
  items: ProcessedItem[]
  total: number
}

function parseGrid(gridStr: string): [number, number] {
  const m = gridStr.match(/(\d+)\s*[×x]\s*(\d+)/)
  return m ? [parseInt(m[1]), parseInt(m[2])] : [8, 8]
}

export const processingApi = {
  list: (params?: { type?: string; status?: string }) =>
    client.get<unknown, { data: TaskListResponse }>('/processing/tasks', { params }),
  get: (taskId: string) =>
    client.get<unknown, { data: ProcessingTask }>(`/processing/tasks/${taskId}`),
  submitClahe: (data: { name: string; input_paths: string[]; params: { clip_limit: number; grid_size: string | [number, number] } }) => {
    const params = {
      clip_limit: data.params.clip_limit,
      grid_size: typeof data.params.grid_size === 'string'
        ? parseGrid(data.params.grid_size)
        : data.params.grid_size,
    }
    return client.post<unknown, { data: ProcessingTask }>('/processing/clahe', { name: data.name, input_paths: data.input_paths, params })
  },
  submitCrop: (data: { name: string; input_paths: string[]; params: { tile_size: number; overlap_ratio: number } }) =>
    client.post<unknown, { data: ProcessingTask }>('/processing/crop', data),
  listFiles: (taskId: string, params?: { sub_dir?: string; page?: number; page_size?: number }) =>
    client.get<unknown, { data: TaskFileList }>(`/processing/tasks/${taskId}/files`, { params }),
  previewUrl: (taskId: string, filename: string, subDir?: string, size = 'medium') => {
    const q = new URLSearchParams({ filename, size })
    if (subDir) q.set('sub_dir', subDir)
    return `/api/processing/tasks/${taskId}/preview?${q.toString()}`
  },
  // 加工数据
  listProcessed: () =>
    client.get<unknown, { data: ProcessedListResponse }>('/processing/processed'),
  getProcessed: (processedId: string) =>
    client.get<unknown, { data: ProcessedItem }>(`/processing/processed/${processedId}`),
  listProcessedFiles: (processedId: string, params?: { sub_dir?: string; page?: number; page_size?: number }) =>
    client.get<unknown, { data: TaskFileList }>(`/processing/processed/${processedId}/files`, { params }),
  deleteProcessed: (processedId: string, deleteOutput = false) =>
    client.delete<unknown, { data: null }>(`/processing/processed/${processedId}`, { params: { delete_output: deleteOutput } }),
}
