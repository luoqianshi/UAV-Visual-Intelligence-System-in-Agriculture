<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '@/components/common/Icon.vue'

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
</script>

<template>
  <aside
    class="w-60 h-screen bg-white border-r border-surface-border flex flex-col sticky top-0 flex-shrink-0"
  >
    <div class="px-5 py-4 border-b border-surface-border">
      <div class="flex items-center gap-2.5">
        <img src="/app-icon-sm.svg" alt="田间智瞰" class="w-8 h-8 flex-shrink-0" />
        <div>
          <div class="font-semibold text-ink-primary text-base tracking-tight">田间智瞰</div>
          <div class="text-xs text-ink-tertiary">UAV智能农业监管系统</div>
        </div>
      </div>
    </div>
    <nav class="flex-1 px-3 py-4 space-y-0.5">
      <router-link
        v-for="item in navItems"
        :key="item.section"
        :to="item.to"
        class="nav-item"
        :class="{ active: isActive(item.section) }"
      >
        <Icon :name="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="px-3 py-3 border-t border-surface-border">
      <div
        class="flex items-center gap-2.5 px-2 py-2 rounded-btn hover:bg-surface-hover cursor-pointer transition-colors"
      >
        <div
          class="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 text-sm font-medium"
        >
          L
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-sm text-ink-primary truncate font-medium">研究员</div>
          <div class="text-xs text-ink-tertiary truncate">甘蔗组</div>
        </div>
        <Icon name="gear" :size="16" class="text-ink-tertiary" />
      </div>
    </div>
  </aside>
</template>
