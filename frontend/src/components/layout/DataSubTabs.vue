<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '@/components/common/Icon.vue'

const route = useRoute()
const isBatches = computed(() =>
  route.path.startsWith('/data/batches') || route.path === '/data/batch-new')
const isProcessed = computed(() => route.path.startsWith('/data/processed'))
</script>

<template>
  <div class="flex items-center gap-1 border-b border-surface-border mb-6">
    <router-link to="/data/batches" class="sub-tab" :class="{ active: isBatches }">
      <Icon name="database" :size="14" /> 原始数据
    </router-link>
    <router-link to="/data/processed" class="sub-tab" :class="{ active: isProcessed }">
      <Icon name="augment" :size="14" /> 加工数据
    </router-link>
  </div>
</template>
