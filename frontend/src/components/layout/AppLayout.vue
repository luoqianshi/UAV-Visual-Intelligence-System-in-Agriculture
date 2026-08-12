<script setup lang="ts">
import Sidebar from './Sidebar.vue'
// 布局壳：左侧 Sidebar（sticky h-screen）+ 右侧主内容区（自然滚动）
</script>

<template>
  <div class="flex min-h-screen w-full items-start">
    <Sidebar />
    <main class="flex-1 min-h-screen p-8 bg-surface-bg/30 min-w-0">
      <slot />
    </main>
  </div>
</template>
