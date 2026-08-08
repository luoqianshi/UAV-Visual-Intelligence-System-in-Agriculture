<script setup lang="ts">
import Sidebar from './Sidebar.vue'
// 布局壳：左侧 Sidebar + 右侧主内容区
</script>

<template>
  <div class="flex">
    <Sidebar />
    <main class="flex-1 p-8 overflow-auto">
      <slot />
    </main>
  </div>
</template>
