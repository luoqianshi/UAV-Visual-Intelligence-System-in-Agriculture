<script setup lang="ts">
import Sidebar from './Sidebar.vue'
// 布局壳：左侧 Sidebar 固定全高 + 右侧主内容区独立滚动
</script>

<template>
  <div class="flex h-screen w-full overflow-hidden">
    <Sidebar />
    <main class="flex-1 h-full min-h-0 overflow-y-auto p-8 bg-surface-bg/30 min-w-0">
      <slot />
    </main>
  </div>
</template>
