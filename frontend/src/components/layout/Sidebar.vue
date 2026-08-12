<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '@/components/common/Icon.vue'

const STORAGE_KEY = 'uav_vis_sidebar_state'
const DEFAULT_WIDTH = 240
const COLLAPSED_WIDTH = 56
const MIN_WIDTH = 200
const MAX_WIDTH = 360

const route = useRoute()

const navItems = [
  { to: '/', label: '首页', icon: 'home', section: 'index' },
  { to: '/data/batches', label: '数据管理', icon: 'dataset', section: 'data' },
  { to: '/process/tasks', label: '数据处理', icon: 'augment', section: 'process' },
  { to: '/dataset/datasets', label: '数据集管理', icon: 'database', section: 'dataset' },
  { to: '/algo/models', label: '算法广场', icon: 'chip', section: 'algo' },
]

function isActive(section: string): boolean {
  const path = route.path
  if (section === 'index') return path === '/'
  return path.split('/')[1] === section
}

// ---- 状态：折叠 + 宽度（持久化到 localStorage） ----
const collapsed = ref(false)
const width = ref(DEFAULT_WIDTH)

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const data = JSON.parse(raw)
    if (typeof data.collapsed === 'boolean') collapsed.value = data.collapsed
    if (typeof data.width === 'number' && data.width >= MIN_WIDTH && data.width <= MAX_WIDTH) {
      width.value = data.width
    }
  } catch {
    // 忽略损坏的 localStorage 数据
  }
}

function saveState() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ collapsed: collapsed.value, width: width.value }),
    )
  } catch {
    // localStorage 可能不可用，忽略
  }
}

onMounted(loadState)
watch([collapsed, width], saveState)

// ---- 拖拽：右侧边缘调整宽度 ----
const isDragging = ref(false)
let dragStartX = 0
let dragStartWidth = 0

function startDrag(e: MouseEvent) {
  if (collapsed.value) return
  e.preventDefault()
  isDragging.value = true
  dragStartX = e.clientX
  dragStartWidth = width.value
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', onDragEnd)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onDragMove(e: MouseEvent) {
  if (!isDragging.value) return
  const dx = e.clientX - dragStartX
  const next = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, dragStartWidth + dx))
  width.value = next
}

function onDragEnd() {
  isDragging.value = false
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
})

// ---- 切换折叠 ----
function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

const currentWidth = computed(() => (collapsed.value ? COLLAPSED_WIDTH : width.value))
</script>

<template>
  <aside
    class="h-screen bg-white border-r border-surface-border flex flex-col sticky top-0 flex-shrink-0 sidebar"
    :class="{ 'sidebar--collapsed': collapsed }"
    :style="{ width: currentWidth + 'px' }"
  >
    <!-- 顶部 Logo / 折叠按钮 -->
    <div
      class="px-5 py-4 border-b border-surface-border flex items-center"
      :class="{ 'justify-center px-0': collapsed }"
    >
      <div v-if="!collapsed" class="flex items-center gap-2.5 min-w-0">
        <img src="/app-icon-sm.svg" alt="田间智瞰" class="w-8 h-8 flex-shrink-0" />
        <div class="min-w-0">
          <div class="font-semibold text-ink-primary text-base tracking-tight truncate">田间智瞰</div>
          <div class="text-xs text-ink-tertiary truncate">UAV智能农业监管系统</div>
        </div>
      </div>
      <img v-else src="/app-icon-sm.svg" alt="田间智瞰" class="w-8 h-8 flex-shrink-0" />
    </div>

    <!-- 导航 -->
    <nav class="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
      <router-link
        v-for="item in navItems"
        :key="item.section"
        :to="item.to"
        class="nav-item"
        :class="{ active: isActive(item.section) }"
        :title="collapsed ? item.label : ''"
      >
        <Icon :name="item.icon" :size="18" class="flex-shrink-0" />
        <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 底部：折叠按钮 + 用户区 -->
    <div class="px-3 py-3 border-t border-surface-border">
      <div
        class="flex items-center gap-2.5 px-2 py-2 rounded-btn hover:bg-surface-hover cursor-pointer transition-colors"
        :class="{ 'justify-center px-0': collapsed }"
        :title="collapsed ? '研究员 · 甘蔗组' : ''"
      >
        <div
          class="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 text-sm font-medium flex-shrink-0"
        >
          L
        </div>
        <div v-if="!collapsed" class="flex-1 min-w-0">
          <div class="text-sm text-ink-primary truncate font-medium">研究员</div>
          <div class="text-xs text-ink-tertiary truncate">甘蔗组</div>
        </div>
        <button
          v-if="!collapsed"
          class="text-ink-tertiary hover:text-ink-primary flex-shrink-0 p-1 rounded hover:bg-surface-bg transition-colors"
          title="设置"
        >
          <Icon name="gear" :size="16" />
        </button>
      </div>
      <button
        @click="toggleCollapsed"
        class="mt-2 w-full flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-btn text-xs text-ink-tertiary hover:bg-surface-hover hover:text-ink-primary transition-colors"
        :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
      >
        <Icon :name="collapsed ? 'chevron-right' : 'chevron-left'" :size="14" />
        <span v-if="!collapsed">收起</span>
      </button>
    </div>

    <!-- 拖拽手柄：右侧边缘 -->
    <div
      v-if="!collapsed"
      class="sidebar-resize-handle"
      @mousedown="startDrag"
    ></div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: relative;
  transition: width 0.2s ease-out;
  overflow: hidden;
}
.sidebar--collapsed {
  transition: width 0.2s ease-out;
}
.sidebar-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  background: transparent;
  transition: background-color 0.15s;
  z-index: 10;
}
.sidebar-resize-handle:hover {
  background-color: #10B981;
}
.sidebar-resize-handle:active {
  background-color: #059669;
}
</style>
