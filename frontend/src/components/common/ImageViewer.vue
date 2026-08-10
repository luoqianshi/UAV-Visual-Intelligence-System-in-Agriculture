<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

// 高清图片查看器：模态弹窗，支持滚轮/手势缩放、拖拽平移、加载状态、平滑动画
const props = withDefaults(
  defineProps<{
    visible: boolean
    src: string
    alt?: string
  }>(),
  {
    alt: '图片预览',
  },
)

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
}>()

// ---- 变换状态 ----
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const rotation = ref(0)

// ---- 交互状态 ----
const isDragging = ref(false)
const isLoading = ref(true)
const hasError = ref(false)
const imgEl = ref<HTMLImageElement | null>(null)
const containerEl = ref<HTMLDivElement | null>(null)

let dragStartX = 0
let dragStartY = 0
let startTranslateX = 0
let startTranslateY = 0
let dragMoved = false // 区分点击与拖拽

// 触摸缩放状态
let pinchStartDist = 0
let pinchStartScale = 1
let lastTouchDist = 0

const MIN_SCALE = 0.2
const MAX_SCALE = 10
const SCALE_STEP = 0.15

const transformStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value}) rotate(${rotation.value}deg)`,
  transition: isDragging.value ? 'none' : 'transform 0.2s ease-out',
  cursor: isDragging.value ? 'grabbing' : scale.value > 1 ? 'grab' : 'zoom-in',
}))

function resetState() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
  rotation.value = 0
  isDragging.value = false
  isLoading.value = true
  hasError.value = false
}

function close() {
  emit('update:visible', false)
}

function zoomIn() {
  scale.value = Math.min(MAX_SCALE, +(scale.value + SCALE_STEP * scale.value).toFixed(3))
}

function zoomOut() {
  scale.value = Math.max(MIN_SCALE, +(scale.value - SCALE_STEP * scale.value).toFixed(3))
  if (scale.value <= 1) {
    translateX.value = 0
    translateY.value = 0
  }
}

function zoomReset() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
}

function rotateLeft() {
  rotation.value -= 90
}

function rotateRight() {
  rotation.value += 90
}

// ---- 滚轮缩放：以鼠标位置为中心 ----
function onWheel(e: WheelEvent) {
  if (!imgEl.value || !containerEl.value) return
  e.preventDefault()

  const rect = containerEl.value.getBoundingClientRect()
  const mouseX = e.clientX - rect.left - rect.width / 2
  const mouseY = e.clientY - rect.top - rect.height / 2

  const delta = e.deltaY < 0 ? 1 + SCALE_STEP : 1 - SCALE_STEP
  const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale.value * delta))
  const ratio = newScale / scale.value

  // 以鼠标位置为缩放原点，调整位移
  translateX.value = mouseX - (mouseX - translateX.value) * ratio
  translateY.value = mouseY - (mouseY - translateY.value) * ratio
  scale.value = newScale
}

// ---- 鼠标拖拽 ----
function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  // 始终记录起点，用于区分点击与拖拽
  dragStartX = e.clientX
  dragStartY = e.clientY
  startTranslateX = translateX.value
  startTranslateY = translateY.value
  dragMoved = false
  if (scale.value <= 1) return
  e.preventDefault()
  isDragging.value = true
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const dx = e.clientX - dragStartX
  const dy = e.clientY - dragStartY
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true
  translateX.value = startTranslateX + dx
  translateY.value = startTranslateY + dy
}

function onMouseUp() {
  isDragging.value = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

// 点击容器空白区域关闭（拖拽后不触发）
function onContainerClick(e: MouseEvent) {
  if (dragMoved) {
    dragMoved = false
    return
  }
  // 仅当点击目标是容器本身（非图片/控件）时关闭
  if (e.target === containerEl.value) {
    close()
  }
}

// ---- 双击放大/还原 ----
function onDblClick(e: MouseEvent) {
  if (!containerEl.value) return
  if (scale.value > 1) {
    zoomReset()
  } else {
    const rect = containerEl.value.getBoundingClientRect()
    const mouseX = e.clientX - rect.left - rect.width / 2
    const mouseY = e.clientY - rect.top - rect.height / 2
    const targetScale = 2.5
    translateX.value = mouseX * (1 - targetScale)
    translateY.value = mouseY * (1 - targetScale)
    scale.value = targetScale
  }
}

// ---- 触摸事件：单指拖拽 + 双指缩放 ----
function getTouchDistance(touches: TouchList): number {
  const dx = touches[0].clientX - touches[1].clientX
  const dy = touches[0].clientY - touches[1].clientY
  return Math.sqrt(dx * dx + dy * dy)
}

function onTouchStart(e: TouchEvent) {
  if (e.touches.length === 1 && scale.value > 1) {
    isDragging.value = true
    dragStartX = e.touches[0].clientX
    dragStartY = e.touches[0].clientY
    startTranslateX = translateX.value
    startTranslateY = translateY.value
  } else if (e.touches.length === 2) {
    isDragging.value = false
    pinchStartDist = getTouchDistance(e.touches)
    pinchStartScale = scale.value
    lastTouchDist = pinchStartDist
  }
}

function onTouchMove(e: TouchEvent) {
  if (e.touches.length === 1 && isDragging.value) {
    e.preventDefault()
    translateX.value = startTranslateX + (e.touches[0].clientX - dragStartX)
    translateY.value = startTranslateY + (e.touches[0].clientY - dragStartY)
  } else if (e.touches.length === 2) {
    e.preventDefault()
    const dist = getTouchDistance(e.touches)
    const ratio = dist / pinchStartDist
    scale.value = Math.max(MIN_SCALE, Math.min(MAX_SCALE, pinchStartScale * ratio))
    lastTouchDist = dist
    if (scale.value <= 1) {
      translateX.value = 0
      translateY.value = 0
    }
  }
}

function onTouchEnd(e: TouchEvent) {
  if (e.touches.length === 0) {
    isDragging.value = false
  } else if (e.touches.length === 1 && scale.value > 1) {
    isDragging.value = true
    dragStartX = e.touches[0].clientX
    dragStartY = e.touches[0].clientY
    startTranslateX = translateX.value
    startTranslateY = translateY.value
  }
}

// ---- 键盘事件 ----
function onKeyDown(e: KeyboardEvent) {
  if (!props.visible) return
  switch (e.key) {
    case 'Escape':
      close()
      break
    case '+':
    case '=':
      zoomIn()
      break
    case '-':
    case '_':
      zoomOut()
      break
    case '0':
      zoomReset()
      break
  }
}

// ---- 图片加载 ----
function onImgLoad() {
  isLoading.value = false
  hasError.value = false
}

function onImgError() {
  isLoading.value = false
  hasError.value = true
}

// ---- 打开/关闭时锁定 body 滚动 ----
watch(
  () => props.visible,
  async (v) => {
    if (v) {
      resetState()
      document.body.style.overflow = 'hidden'
      window.addEventListener('keydown', onKeyDown)
      await nextTick()
    } else {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  },
)

// 切换图片时重置加载状态
watch(
  () => props.src,
  () => {
    if (props.visible) {
      isLoading.value = true
      hasError.value = false
      scale.value = 1
      translateX.value = 0
      translateY.value = 0
    }
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="iv-fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-[9999] flex items-center justify-center"
        role="dialog"
        aria-modal="true"
        @click.self="close"
      >
        <!-- 半透明遮罩 -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm"></div>

        <!-- 顶部工具栏 -->
        <div class="iv-toolbar absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-3">
          <div class="text-white/80 text-xs truncate max-w-[60%] flex items-center gap-2">
            <i class="fa-solid fa-image text-brand-300"></i>
            <span>{{ alt }}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <button
              class="iv-btn"
              title="缩小 (-)"
              @click="zoomOut"
            >
              <i class="fa-solid fa-magnifying-glass-minus"></i>
            </button>
            <button
              class="iv-btn iv-btn-text"
              title="重置 (0)"
              @click="zoomReset"
            >
              {{ Math.round(scale * 100) }}%
            </button>
            <button
              class="iv-btn"
              title="放大 (+)"
              @click="zoomIn"
            >
              <i class="fa-solid fa-magnifying-glass-plus"></i>
            </button>
            <div class="w-px h-5 bg-white/20 mx-1"></div>
            <button
              class="iv-btn"
              title="向左旋转"
              @click="rotateLeft"
            >
              <i class="fa-solid fa-rotate-left"></i>
            </button>
            <button
              class="iv-btn"
              title="向右旋转"
              @click="rotateRight"
            >
              <i class="fa-solid fa-rotate-right"></i>
            </button>
            <div class="w-px h-5 bg-white/20 mx-1"></div>
            <button
              class="iv-btn iv-btn-close"
              title="关闭 (Esc)"
              @click="close"
            >
              <i class="fa-solid fa-xmark text-lg"></i>
            </button>
          </div>
        </div>

        <!-- 图片容器 -->
        <div
          ref="containerEl"
          class="relative w-full h-full flex items-center justify-center overflow-hidden select-none"
          @wheel="onWheel"
          @mousedown="onMouseDown"
          @click="onContainerClick"
          @dblclick="onDblClick"
          @touchstart="onTouchStart"
          @touchmove="onTouchMove"
          @touchend="onTouchEnd"
        >
          <!-- 加载状态 -->
          <div
            v-if="isLoading && !hasError"
            class="absolute inset-0 flex flex-col items-center justify-center gap-3 z-[5]"
          >
            <i class="fa-solid fa-circle-notch fa-spin text-4xl text-brand-300"></i>
            <span class="text-white/70 text-sm">图片加载中…</span>
          </div>

          <!-- 错误状态 -->
          <div
            v-if="hasError"
            class="absolute inset-0 flex flex-col items-center justify-center gap-3 z-[5]"
          >
            <i class="fa-solid fa-circle-exclamation text-4xl text-red-400"></i>
            <span class="text-white/70 text-sm">图片加载失败</span>
          </div>

          <!-- 图片本体 -->
          <img
            v-if="src"
            ref="imgEl"
            :src="src"
            :alt="alt"
            class="iv-image max-w-[90vw] max-h-[85vh] object-contain"
            :style="transformStyle"
            draggable="false"
            @load="onImgLoad"
            @error="onImgError"
            @dragstart.prevent
          />
        </div>

        <!-- 底部提示 -->
        <div class="absolute bottom-0 left-0 right-0 z-10 flex justify-center pb-4 pointer-events-none">
          <div
            class="bg-black/40 text-white/60 text-xs px-4 py-1.5 rounded-full backdrop-blur-sm flex items-center gap-4"
          >
            <span><i class="fa-solid fa-magnifying-glass mr-1"></i>滚轮缩放</span>
            <span><i class="fa-solid fa-hand mr-1"></i>拖拽移动</span>
            <span><i class="fa-solid fa-hand-pointer mr-1"></i>双击放大</span>
            <span><kbd class="iv-kbd">Esc</kbd> 关闭</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.iv-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.15s;
  cursor: pointer;
  font-size: 13px;
}
.iv-btn:hover {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}
.iv-btn:active {
  transform: scale(0.95);
}
.iv-btn-text {
  width: auto;
  padding: 0 10px;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}
.iv-btn-close {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
}
.iv-btn-close:hover {
  background: rgba(239, 68, 68, 0.4);
}

.iv-kbd {
  display: inline-block;
  padding: 1px 6px;
  font-family: ui-monospace, monospace;
  font-size: 10px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.iv-image {
  will-change: transform;
  -webkit-user-drag: none;
  user-select: none;
}

/* 过渡动画 */
.iv-fade-enter-active,
.iv-fade-leave-active {
  transition: opacity 0.22s ease;
}
.iv-fade-enter-active .iv-image,
.iv-fade-leave-active .iv-image {
  transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.22s ease;
}
.iv-fade-enter-from,
.iv-fade-leave-to {
  opacity: 0;
}
.iv-fade-enter-from .iv-image {
  transform: scale(0.92);
  opacity: 0;
}
.iv-fade-leave-to .iv-image {
  transform: scale(0.96);
  opacity: 0;
}

.iv-toolbar {
  animation: iv-slide-down 0.25s ease-out;
}
@keyframes iv-slide-down {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
