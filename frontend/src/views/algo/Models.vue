<script setup lang="ts">
import { onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import { useModelStore } from '@/stores/model'
import type { ModelConfig } from '@/api/models'
import Icon from '@/components/common/Icon.vue'

const modelStore = useModelStore()

onMounted(() => {
  modelStore.fetchModels()
})

async function onSwitch(m: ModelConfig) {
  try {
    await modelStore.switchModel(m.name)
  } catch (e) {
    // 错误由 store 抛出
  }
}
</script>

<template>
  <AppLayout>
    <div class="flex items-end justify-between mb-5">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">算法广场</div>
        <h1 class="text-2xl font-bold text-ink-primary tracking-tight">算法管理</h1>
        <p class="text-sm text-ink-secondary mt-1.5">
          管理甘蔗幼苗检测模型权重 · 当前激活：<span class="text-brand-700 font-semibold">{{ modelStore.currentModel || '—' }}</span>
        </p>
      </div>
      <router-link
        to="/algo/model-register"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold inline-flex items-center gap-2 transition-colors"
      >
        <Icon name="plus" :size="14" /> 注册模型
      </router-link>
    </div>

    <SubTabs />

    <div class="grid grid-cols-4 gap-4 mb-5">
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">注册模型</div>
            <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">{{ modelStore.models.length }}</div>
          </div>
          <div class="w-9 h-9 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
            <Icon name="nn" :size="18" />
          </div>
        </div>
        <div class="text-xs text-ink-tertiary mt-2">全部为甘蔗幼苗检测</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">支持框架</div>
            <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">2</div>
          </div>
          <div class="w-9 h-9 rounded-btn bg-blue-50 flex items-center justify-center text-blue-600">
            <Icon name="chip" :size="18" />
          </div>
        </div>
        <div class="text-xs text-ink-tertiary mt-2">Ultralytics · Custom</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">最佳 mAP@0.5</div>
            <div class="text-2xl font-bold text-brand-700 mt-1 font-numeric">0.884</div>
          </div>
          <div class="w-9 h-9 rounded-btn bg-amber-50 flex items-center justify-center text-amber-600">
            <Icon name="target" :size="18" />
          </div>
        </div>
        <div class="text-xs text-ink-tertiary mt-2">YOLO12s-sugarcane</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">推理设备</div>
            <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">GPU×1</div>
          </div>
          <div class="w-9 h-9 rounded-btn bg-purple-50 flex items-center justify-center text-purple-600">
            <Icon name="augment" :size="18" />
          </div>
        </div>
        <div class="text-xs text-ink-tertiary mt-2">NVIDIA RTX 4060 Ti 16G</div>
      </div>
    </div>

    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-3 px-5 font-medium">模型名称</th>
            <th class="text-left py-3 px-5 font-medium">框架 / 规格</th>
            <th class="text-left py-3 px-5 font-medium">类别</th>
            <th class="text-left py-3 px-5 font-medium">推理参数</th>
            <th class="text-left py-3 px-5 font-medium">状态</th>
            <th class="text-left py-3 px-5 font-medium">更新时间</th>
            <th class="text-right py-3 px-5 font-medium w-32">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr
            v-for="m in modelStore.models"
            :key="m.name"
            class="border-t border-surface-border"
            :class="{ 'bg-brand-50/30': m.is_active }"
          >
            <td class="py-3 px-5">
              <div class="flex items-center gap-3">
                <div
                  class="w-8 h-8 rounded-btn flex items-center justify-center"
                  :class="m.is_active ? 'bg-brand-50' : 'bg-surface-bg'"
                >
                  <Icon name="seedling" :size="16" :color="m.is_active ? '#10B981' : '#9CA3AF'" />
                </div>
                <div>
                  <router-link
                    :to="`/algo/models/${m.name}`"
                    class="font-medium text-ink-primary hover:text-brand-700 transition-colors"
                  >
                    {{ m.display_name || m.name }}
                  </router-link>
                  <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ m.name }} · {{ m.category || '—' }}</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-5">
              <div class="text-ink-primary text-xs font-medium">{{ m.engine }}</div>
              <div class="text-ink-tertiary text-xs font-numeric">imgsz {{ m.imgsz }}</div>
            </td>
            <td class="py-3 px-5">
              <span class="text-xs text-ink-secondary">{{ m.category || '—' }}</span>
            </td>
            <td class="py-3 px-5">
              <div class="font-semibold text-brand-700 font-numeric">conf {{ m.conf }}</div>
              <div class="text-xs text-ink-tertiary font-numeric">iou {{ m.iou }} · max {{ m.max_det }}</div>
            </td>
            <td class="py-3 px-5">
              <span v-if="m.is_active" class="badge badge-success">
                <span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span> 已激活
              </span>
              <span v-else class="badge badge-info">已发布</span>
            </td>
            <td class="py-3 px-5 text-xs text-ink-secondary">—</td>
            <td class="py-3 px-5 text-right">
              <div class="flex items-center justify-end gap-3">
                <router-link
                  :to="`/algo/models/${m.name}`"
                  class="text-xs text-brand-700 hover:underline font-medium"
                >详情</router-link>
                <button
                  v-if="!m.is_active"
                  class="text-xs text-brand-700 hover:underline font-medium"
                  @click="onSwitch(m)"
                >激活</button>
              </div>
            </td>
          </tr>
          <tr v-if="modelStore.models.length === 0 && !modelStore.loading">
            <td colspan="7" class="py-12 text-center text-sm text-ink-tertiary">
              <Icon name="folder-open" :size="32" class="text-ink-tertiary opacity-30 mb-2 mx-auto" />
              暂无已注册模型，点击右上角「注册模型」添加
            </td>
          </tr>
          <tr v-if="modelStore.loading && modelStore.models.length === 0">
            <td colspan="7" class="py-12 text-center text-sm text-ink-tertiary">
              <Icon name="spinner" :size="28" class="text-brand-300 mb-2 mx-auto animate-spin-slow" />
              加载中…
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>
