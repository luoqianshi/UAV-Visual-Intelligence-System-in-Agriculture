<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

// 算法广场双子栏目：算法管理 / 作物计数
const route = useRoute()
const isCounting = computed(() => route.path.startsWith('/algo/counting'))
</script>

<template>
  <div class="flex items-center gap-1 border-b border-surface-border mb-6">
    <router-link to="/algo/models" class="sub-tab" :class="{ active: !isCounting }">
      <i class="fa-solid fa-microchip text-xs"></i>算法管理
    </router-link>
    <router-link to="/algo/counting" class="sub-tab" :class="{ active: isCounting }">
      <i class="fa-solid fa-calculator text-xs"></i>作物计数
    </router-link>
  </div>
</template>
