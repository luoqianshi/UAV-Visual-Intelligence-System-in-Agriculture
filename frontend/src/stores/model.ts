import { defineStore } from 'pinia'
import { ref } from 'vue'
import { modelsApi, type ModelConfig, type RegisterModelForm } from '@/api/models'

export const useModelStore = defineStore('model', () => {
  const models = ref<ModelConfig[]>([])
  const currentModel = ref<string>('')
  const loading = ref(false)

  async function fetchModels() {
    loading.value = true
    try {
      const res = await modelsApi.list()
      models.value = res.data.models
      currentModel.value = res.data.current_model
    } finally {
      loading.value = false
    }
  }

  async function switchModel(name: string) {
    const res = await modelsApi.switch(name)
    models.value = res.data.models
    currentModel.value = res.data.current_model
    return res.data
  }

  async function registerModel(form: RegisterModelForm) {
    const formData = new FormData()
    formData.append('name', form.name.trim())
    formData.append('display_name', form.display_name.trim() || form.name.trim())
    formData.append('engine', form.engine)
    formData.append('category', form.category.trim())
    formData.append('classes', form.classes)
    formData.append('imgsz', String(form.imgsz))
    formData.append('conf', String(form.conf))
    formData.append('iou', String(form.iou))
    formData.append('max_det', String(form.max_det))
    if (form.device) {
      formData.append('device', form.device)
    }
    if (form.weight_file) {
      formData.append('weight_file', form.weight_file)
    }
    const res = await modelsApi.register(formData)
    models.value = res.data.models
    currentModel.value = res.data.current_model
    return res.data
  }

  return { models, currentModel, loading, fetchModels, switchModel, registerModel }
})
