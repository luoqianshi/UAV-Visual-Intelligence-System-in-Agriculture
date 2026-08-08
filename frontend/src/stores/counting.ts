import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'
import { countingApi, type CountingReport, type CountingParams } from '@/api/counting'

export const useCountingStore = defineStore('counting', () => {
  const taskId = ref('')
  const status = ref<'idle' | 'pending' | 'processing' | 'completed' | 'failed'>('idle')
  const progress = ref(0)
  const error = ref('')
  const result = shallowRef<CountingReport | null>(null)
  const history = ref<any[]>([])

  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function submit(payload: { image_path?: string; image_dir?: string; model_name?: string } & CountingParams) {
    error.value = ''
    result.value = null
    progress.value = 0
    status.value = 'pending'
    taskId.value = ''
    const res = await countingApi.submit(payload)
    taskId.value = res.data.task_id
    startPolling()
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(async () => {
      if (!taskId.value) return
      try {
        const res = await countingApi.getTask(taskId.value)
        status.value = res.data.status
        progress.value = res.data.progress
        if (res.data.status === 'completed') {
          stopPolling()
          const resultRes = await countingApi.getResult(taskId.value)
          result.value = resultRes.data
        } else if (res.data.status === 'failed') {
          stopPolling()
          error.value = res.data.error || '计数任务失败'
        }
      } catch (e: any) {
        stopPolling()
        status.value = 'failed'
        error.value = e.message
      }
    }, 1500)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function fetchHistory() {
    const res = await countingApi.history()
    history.value = res.data
  }

  return { taskId, status, progress, error, result, history, submit, stopPolling, fetchHistory }
})
