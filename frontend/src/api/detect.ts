import client from './client'

export interface Detection {
  x: number
  y: number
  width: number
  height: number
  confidence: number
  class: number
  class_name: string
}

export interface DetectResult {
  detection_count: number
  result_image: string | null
  detection_data: Detection[]
  model_info: { name: string; display_name: string; imgsz: number }
}

export interface TaskStatus {
  task_id: string
  task_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  result: any
  error: string | null
}

export const detectApi = {
  // 单图同步检测（multipart）
  detectSingle: (file: File, model_name?: string, params?: Record<string, any>) => {
    const form = new FormData()
    form.append('image', file)
    if (model_name) form.append('model_name', model_name)
    if (params) {
      for (const [k, v] of Object.entries(params)) form.append(k, String(v))
    }
    return client.post<unknown, { data: DetectResult }>('/detect', form)
  },
  // 批量异步检测（目录）
  detectBatch: (image_dir: string, model_name?: string, params?: Record<string, any>) =>
    client.post<unknown, { data: { task_id: string } }>('/detect', { image_dir, model_name, ...params }),
  getTask: (task_id: string) => client.get<unknown, { data: TaskStatus }>(`/detect/tasks/${task_id}`),
  getResult: (task_id: string) => client.get<unknown, { data: any }>(`/detect/tasks/${task_id}/result`),
}
