import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { detectApi, type DetectResult, type TaskStatus } from '@/api/detect'

export const useDetectStore = defineStore('detect', () => {
  const result = shallowRef<DetectResult | null>(null)
  const loading = ref(false)
  const error = ref('')

  // 批量异步
  const batchTaskId = ref('')
  const batchStatus = ref<TaskStatus | null>(null)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function detectSingle(file: File, model_name?: string, params?: Record<string, any>) {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const res = await detectApi.detectSingle(file, model_name, params)
      result.value = res.data
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function detectBatch(image_dir: string, model_name?: string, params?: Record<string, any>) {
    error.value = ''
    batchTaskId.value = ''
    batchStatus.value = null
    const res = await detectApi.detectBatch(image_dir, model_name, params)
    batchTaskId.value = res.data.task_id
    startPolling()
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(async () => {
      if (!batchTaskId.value) return
      try {
        const res = await detectApi.getTask(batchTaskId.value)
        batchStatus.value = res.data
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          stopPolling()
        }
      } catch {
        stopPolling()
      }
    }, 1500)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  return { result, loading, error, batchTaskId, batchStatus, detectSingle, detectBatch, stopPolling }
})
