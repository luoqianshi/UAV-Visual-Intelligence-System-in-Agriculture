<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '@/components/common/Icon.vue'

const route = useRoute()
const isModels = computed(() => route.path.startsWith('/algo/models'))
const isDetect = computed(() => route.path === '/algo/detect')
const isCounting = computed(() => route.path.startsWith('/algo/counting'))
</script>

<template>
  <div class="flex items-center gap-1 border-b border-surface-border mb-6">
    <router-link to="/algo/models" class="sub-tab" :class="{ active: isModels }">
      <Icon name="chip" :size="14" />算法管理
    </router-link>
    <router-link to="/algo/detect" class="sub-tab" :class="{ active: isDetect }">
      <Icon name="target" :size="14" />作物检测
    </router-link>
    <router-link to="/algo/counting" class="sub-tab" :class="{ active: isCounting }">
      <Icon name="count" :size="14" />作物计数
    </router-link>
  </div>
</template>
