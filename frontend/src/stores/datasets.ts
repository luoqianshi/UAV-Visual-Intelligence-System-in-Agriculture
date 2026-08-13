import { defineStore } from 'pinia'
import { ref } from 'vue'
import { datasetsApi, type Dataset } from '@/api/datasets'

export const useDatasetsStore = defineStore('datasets', () => {
  const datasets = ref<Dataset[]>([])
  const total = ref(0)
  const formatDist = ref<Record<string, number>>({ YOLO: 0, COCO: 0, VOC: 0 })
  const loading = ref(false)
  const error = ref('')

  async function fetchDatasets(params?: { format?: string }) {
    loading.value = true
    error.value = ''
    try {
      const res = await datasetsApi.fetchDatasets(params)
      datasets.value = res.data.datasets
      total.value = res.data.total
      formatDist.value = res.data.format_dist
    } catch (e: any) {
      error.value = e.message || '加载失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  return { datasets, total, formatDist, loading, error, fetchDatasets }
})
