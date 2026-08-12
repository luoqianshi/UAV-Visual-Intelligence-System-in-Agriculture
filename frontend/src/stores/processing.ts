import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { processingApi, type ProcessingTask } from '@/api/processing'

export const useProcessingStore = defineStore('processing', () => {
  const tasks = ref<ProcessingTask[]>([])
  const loading = ref(false)
  const error = ref('')
  const filterType = ref('')
  const filterStatus = ref('')

  const taskTotal = computed(() => tasks.value.length)

  async function fetchTasks(params?: { type?: string; status?: string }) {
    loading.value = true
    error.value = ''
    try {
      const res = await processingApi.list(params)
      tasks.value = res.data.tasks
    } catch (e: any) {
      error.value = e.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function applyFilters() {
    await fetchTasks({
      type: filterType.value || undefined,
      status: filterStatus.value || undefined,
    })
  }

  return {
    tasks,
    loading,
    error,
    filterType,
    filterStatus,
    taskTotal,
    fetchTasks,
    applyFilters,
  }
})
