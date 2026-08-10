import client from './client'

export interface ModelConfig {
  name: string
  engine: string
  weight: string
  display_name: string
  category: string
  imgsz: number
  conf: number
  iou: number
  device: string | null
  classes: string[]
  max_det: number
  is_active?: boolean
}

export interface ModelsResponse {
  models: ModelConfig[]
  current_model: string
}

export interface RegisterModelForm {
  name: string
  display_name: string
  engine: string
  category: string
  classes: string
  imgsz: number
  conf: number
  iou: number
  max_det: number
  device: string
  weight_file?: File
}

export const modelsApi = {
  list: () => client.get<unknown, { data: ModelsResponse }>('/models'),
  switch: (model_name: string) => client.post<unknown, { data: ModelsResponse }>('/models/switch', { model_name }),
  register: (formData: FormData) => client.post<unknown, { data: ModelsResponse }>('/models/load', formData),
  health: () => client.get<unknown, { data: any }>('/health'),
}
