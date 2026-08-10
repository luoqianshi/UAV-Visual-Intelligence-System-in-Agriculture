<script setup lang="ts">
import { ref } from 'vue'
import ImageViewer from '@/components/common/ImageViewer.vue'

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

// ---- 高清大图弹窗 ----
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')

function openViewer(src: string, alt: string) {
  if (!src) return
  viewerSrc.value = src
  viewerAlt.value = alt
  viewerVisible.value = true
}
</script>

<template>
  <div class="grid grid-cols-2 gap-4">
    <!-- 原图 -->
    <div>
      <div class="text-xs text-ink-tertiary mb-2 flex items-center justify-between">
        <span>{{ originalLabel }}</span>
        <span
          v-if="originalImage"
          class="text-[10px] text-brand-700/70 inline-flex items-center gap-1 cursor-help"
          title="点击图片可查看高清大图"
        >
          <i class="fa-solid fa-magnifying-glass-plus"></i> 点击放大
        </span>
      </div>
      <div
        class="aspect-[4/3] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border overflow-hidden relative group"
        :class="{ 'cursor-zoom-in': originalImage }"
        @click="openViewer(originalImage || '', originalLabel)"
      >
        <img
          v-if="originalImage"
          :src="originalImage"
          alt="原图"
          class="w-full h-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
        />
        <div v-else class="flex flex-col items-center justify-center gap-2 text-center px-3">
          <i class="fa-solid fa-image text-4xl text-ink-tertiary opacity-30"></i>
          <span class="text-xs text-ink-tertiary">{{ originalEmptyText }}</span>
        </div>

        <!-- 悬停放大提示遮罩 -->
        <div
          v-if="originalImage"
          class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100 pointer-events-none"
        >
          <span class="bg-black/60 text-white text-xs px-2.5 py-1 rounded-full inline-flex items-center gap-1.5">
            <i class="fa-solid fa-magnifying-glass-plus text-[10px]"></i>
            查看大图
          </span>
        </div>
      </div>
    </div>

    <!-- 检测结果图 -->
    <div>
      <div class="text-xs text-ink-tertiary mb-2 flex items-center justify-between">
        <span>{{ resultLabel }}</span>
        <span
          v-if="resultImage"
          class="text-[10px] text-brand-700/70 inline-flex items-center gap-1 cursor-help"
          title="点击图片可查看高清大图"
        >
          <i class="fa-solid fa-magnifying-glass-plus"></i> 点击放大
        </span>
      </div>
      <div
        class="aspect-[4/3] rounded-btn flex items-center justify-center border border-surface-border overflow-hidden bg-surface-bg relative group"
        :class="{ 'cursor-zoom-in': resultImage }"
        @click="openViewer(getResultSrc(), resultLabel)"
      >
        <img
          v-if="resultImage"
          :src="getResultSrc()"
          alt="检测结果"
          class="w-full h-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
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

        <!-- 悬停放大提示遮罩 -->
        <div
          v-if="resultImage && !loading"
          class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100 pointer-events-none"
        >
          <span class="bg-black/60 text-white text-xs px-2.5 py-1 rounded-full inline-flex items-center gap-1.5">
            <i class="fa-solid fa-magnifying-glass-plus text-[10px]"></i>
            查看大图
          </span>
        </div>
      </div>
    </div>

    <!-- 高清大图弹窗 -->
    <ImageViewer
      v-model:visible="viewerVisible"
      :src="viewerSrc"
      :alt="viewerAlt"
    />
  </div>
</template>
