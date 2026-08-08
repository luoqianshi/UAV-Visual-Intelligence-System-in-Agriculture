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
  device: string
  classes: string[]
  max_det: number
  half: boolean
  is_active?: boolean
}

export interface ModelsResponse {
  models: ModelConfig[]
  current_model: string
}

export const modelsApi = {
  list: () => client.get<unknown, { data: ModelsResponse }>('/models'),
  switch: (model_name: string) => client.post<unknown, { data: ModelsResponse }>('/models/switch', { model_name }),
  load: (config: Partial<ModelConfig>) => client.post<unknown, { data: ModelsResponse }>('/models/load', config),
  health: () => client.get<unknown, { data: any }>('/health'),
}
