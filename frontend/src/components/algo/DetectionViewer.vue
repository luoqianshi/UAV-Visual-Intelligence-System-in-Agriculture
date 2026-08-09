<script setup lang="ts">
// 检测结果图像查看器：纯展示组件，左原图 / 右检测结果图
const props = withDefaults(defineProps<{
  originalImage?: string // 上传文件的 object URL（或 base64）
  resultImage?: string | null // 后端返回的 base64 jpeg
  loading?: boolean
  originalEmptyText?: string
  resultEmptyText?: string
  originalLabel?: string
  resultLabel?: string
  showCountBadge?: boolean
  count?: number
}>(), {
  originalEmptyText: '等待上传',
  resultEmptyText: '等待检测',
  originalLabel: '原图',
  resultLabel: '检测结果（红色框）',
  showCountBadge: false,
  count: 0,
})

function getResultSrc() {
  if (!props.resultImage) return ''
  return props.resultImage.startsWith('data:')
    ? props.resultImage
    : `data:image/jpeg;base64,${props.resultImage}`
}
</script>

<template>
  <div class="grid grid-cols-2 gap-4">
    <!-- 原图 -->
    <div>
      <div class="text-xs text-ink-tertiary mb-2">{{ originalLabel }}</div>
      <div
        class="aspect-[4/3] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border overflow-hidden relative"
      >
        <img
          v-if="originalImage"
          :src="originalImage"
          alt="原图"
          class="w-full h-full object-contain"
        />
        <div v-else class="flex flex-col items-center justify-center gap-2 text-center px-3">
          <i class="fa-solid fa-image text-4xl text-ink-tertiary opacity-30"></i>
          <span class="text-xs text-ink-tertiary">{{ originalEmptyText }}</span>
        </div>
      </div>
    </div>

    <!-- 检测结果图 -->
    <div>
      <div class="text-xs text-ink-tertiary mb-2">{{ resultLabel }}</div>
      <div
        class="aspect-[4/3] rounded-btn flex items-center justify-center border border-surface-border overflow-hidden bg-surface-bg relative"
      >
        <img
          v-if="resultImage"
          :src="getResultSrc()"
          alt="检测结果"
          class="w-full h-full object-contain"
        />
        <div v-else class="flex flex-col items-center justify-center gap-2">
          <i class="fa-solid fa-image text-4xl text-ink-tertiary opacity-30"></i>
          <span class="text-xs text-ink-tertiary">{{ resultEmptyText }}</span>
        </div>

        <!-- 计数标注徽章 -->
        <div
          v-if="showCountBadge && count"
          class="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded"
        >
          共标注 {{ count }} 个目标
        </div>

        <!-- 检测中遮罩 -->
        <div
          v-if="loading"
          class="absolute inset-0 bg-white/60 backdrop-blur-sm flex flex-col items-center justify-center gap-2"
        >
          <i class="fa-solid fa-circle-notch fa-spin text-2xl text-brand-700"></i>
          <span class="text-xs text-ink-secondary">处理中…</span>
        </div>
      </div>
    </div>
  </div>
</template>
