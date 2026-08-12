import { defineStore } from 'pinia'
import { ref } from 'vue'
import { mockApi, type Dataset } from '@/api/mock'

export const useMockStore = defineStore('mock', () => {
  const datasets = ref<Dataset[]>([])
  const datasetTotal = ref(0)
  const formatDist = ref<Record<string, number>>({})
  const loading = ref(false)

  async function fetchDatasets(params?: { format?: string }) {
    loading.value = true
    try {
      const res = await mockApi.fetchDatasets(params)
      datasets.value = res.data.datasets
      datasetTotal.value = res.data.total
      formatDist.value = res.data.format_dist
    } finally {
      loading.value = false
    }
  }

  return {
    datasets, datasetTotal, formatDist, loading,
    fetchDatasets,
  }
})
