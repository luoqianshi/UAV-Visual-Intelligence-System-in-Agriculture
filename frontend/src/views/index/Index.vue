<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { useModelStore } from '@/stores/model'
import { onMounted, ref } from 'vue'

const modelStore = useModelStore()
const health = ref<string>('检查中…')

onMounted(async () => {
  try {
    await modelStore.fetchModels()
    health.value = `已加载 ${modelStore.models.length} 个模型，激活：${modelStore.currentModel}`
  } catch (e: any) {
    health.value = `后端未连接：${e.message}`
  }
})
</script>

<template>
  <AppLayout>
    <h1 class="text-2xl font-semibold text-ink-primary">田间智监 · 脚手架冒烟测试</h1>
    <p class="text-sm text-ink-secondary mt-2">{{ health }}</p>
    <div class="mt-4 bg-brand-50 border border-brand-300 rounded-card p-4 text-brand-700">
      Tailwind 色板 + AppLayout + Pinia + API 联调验证
    </div>
  </AppLayout>
</template>
