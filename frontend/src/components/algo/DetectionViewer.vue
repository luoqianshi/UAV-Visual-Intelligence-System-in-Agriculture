<script setup lang="ts">
// 检测结果图像查看器：纯展示组件，左原图 / 右检测结果图
// 1:1 迁移 algo/detect.html 的「结果展示」图像面板样式
const props = defineProps<{
  originalImage?: string // 上传文件的 object URL（或 base64）
  resultImage?: string | null // 后端返回的 base64 jpeg
  loading?: boolean
}>()
</script>

<template>
  <div class="grid grid-cols-2 gap-4">
    <!-- 原图 -->
    <div>
      <div class="text-xs text-ink-tertiary mb-2">原图</div>
      <div
        class="aspect-[4/3] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border overflow-hidden relative"
      >
        <img
          v-if="props.originalImage"
          :src="props.originalImage"
          alt="原图"
          class="w-full h-full object-contain"
        />
        <div v-else class="flex flex-col items-center justify-center gap-2">
          <i class="fa-solid fa-image text-4xl text-ink-tertiary opacity-30"></i>
          <span class="text-xs text-ink-tertiary">等待上传</span>
        </div>
      </div>
    </div>

    <!-- 检测结果图 -->
    <div>
      <div class="text-xs text-ink-tertiary mb-2">检测结果（红色框 2px）</div>
      <div
        class="aspect-[4/3] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border overflow-hidden relative"
      >
        <img
          v-if="props.resultImage"
          :src="'data:image/jpeg;base64,' + props.resultImage"
          alt="检测结果"
          class="w-full h-full object-contain"
        />
        <div v-else class="flex flex-col items-center justify-center gap-2">
          <i class="fa-solid fa-image text-4xl text-ink-tertiary opacity-30"></i>
          <span class="text-xs text-ink-tertiary">等待检测</span>
        </div>

        <!-- 检测中遮罩 -->
        <div
          v-if="props.loading"
          class="absolute inset-0 bg-white/60 backdrop-blur-sm flex flex-col items-center justify-center gap-2"
        >
          <i class="fa-solid fa-circle-notch fa-spin text-2xl text-brand-700"></i>
          <span class="text-xs text-ink-secondary">检测中…</span>
        </div>
      </div>
    </div>
  </div>
</template>
