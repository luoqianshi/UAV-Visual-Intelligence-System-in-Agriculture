import { defineStore } from 'pinia'
import { ref } from 'vue'
import { modelsApi, type ModelConfig } from '@/api/models'

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

  async function registerModel(config: Partial<ModelConfig>) {
    const res = await modelsApi.load(config)
    models.value = res.data.models
    currentModel.value = res.data.current_model
    return res.data
  }

  return { models, currentModel, loading, fetchModels, switchModel, registerModel }
})
