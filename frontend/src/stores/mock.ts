import { defineStore } from 'pinia'
import { ref } from 'vue'
import { mockApi, type Batch, type ProcessingTask, type Dataset } from '@/api/mock'

export const useMockStore = defineStore('mock', () => {
  const batches = ref<Batch[]>([])
  const batchTotal = ref(0)
  const tasks = ref<ProcessingTask[]>([])
  const taskTotal = ref(0)
  const datasets = ref<Dataset[]>([])
  const datasetTotal = ref(0)
  const formatDist = ref<Record<string, number>>({})
  const loading = ref(false)

  async function fetchBatches(params?: { crop_type?: string; status?: string }) {
    loading.value = true
    try {
      const res = await mockApi.fetchBatches(params)
      batches.value = res.data.batches
      batchTotal.value = res.data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchTasks(params?: { type?: string; status?: string }) {
    loading.value = true
    try {
      const res = await mockApi.fetchTasks(params)
      tasks.value = res.data.tasks
      taskTotal.value = res.data.total
    } finally {
      loading.value = false
    }
  }

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
    batches, batchTotal, tasks, taskTotal, datasets, datasetTotal, formatDist, loading,
    fetchBatches, fetchTasks, fetchDatasets,
  }
})
