<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

// 1:1 迁移 V0.4 侧边栏：🌾 logo + 5 导航 + 底部用户区
const route = useRoute()

const navItems = [
  { to: '/', label: '首页', icon: 'fa-house', section: 'index' },
  { to: '/data/batches', label: '数据管理', icon: 'fa-folder-open', section: 'data' },
  { to: '/process/tasks', label: '数据处理', icon: 'fa-wand-magic-sparkles', section: 'process' },
  { to: '/dataset/datasets', label: '数据集管理', icon: 'fa-database', section: 'dataset' },
  { to: '/algo/models', label: '算法广场', icon: 'fa-microchip', section: 'algo' },
]

function isActive(section: string): boolean {
  const path = route.path
  if (section === 'index') return path === '/'
  return path.split('/')[1] === section
}
</script>

<template>
  <aside
    class="w-60 h-screen bg-white border-r border-surface-border flex flex-col sticky top-0 flex-shrink-0"
  >
    <div class="px-5 py-4 border-b border-surface-border">
      <div class="flex items-center gap-2">
        <img src="/app-icon-sm.svg" alt="田间智瞰" class="w-8 h-8 flex-shrink-0" />
        <div>
          <div class="font-semibold text-ink-primary text-base">田间智瞰</div>
          <div class="text-xs text-ink-tertiary">UAV智能农业监管系统</div>
        </div>
      </div>
    </div>
    <nav class="flex-1 px-3 py-4 space-y-1">
      <router-link
        v-for="item in navItems"
        :key="item.section"
        :to="item.to"
        class="nav-item"
        :class="{ active: isActive(item.section) }"
      >
        <i class="fa-solid text-base w-5" :class="item.icon"></i>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="px-3 py-3 border-t border-surface-border">
      <div
        class="flex items-center gap-2 px-2 py-2 rounded-btn hover:bg-surface-hover cursor-pointer"
      >
        <div
          class="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 text-sm font-medium"
        >
          L
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-sm text-ink-primary truncate">研究员</div>
          <div class="text-xs text-ink-tertiary truncate">甘蔗组</div>
        </div>
        <i class="fa-solid fa-gear text-ink-tertiary text-sm"></i>
      </div>
    </div>
  </aside>
</template>
