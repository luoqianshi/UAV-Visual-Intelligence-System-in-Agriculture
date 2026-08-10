<script setup lang="ts">
import { onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import { useModelStore } from '@/stores/model'
import type { ModelConfig } from '@/api/models'

const modelStore = useModelStore()

onMounted(() => {
  modelStore.fetchModels()
})

async function onSwitch(m: ModelConfig) {
  try {
    await modelStore.switchModel(m.name)
  } catch (e) {
    // 错误由 store 抛出，此处静默；UI 状态以 currentModel 为准
  }
}
</script>

<template>
  <AppLayout>
    <!-- 页头：面包屑 + 标题 + 当前激活模型 + 注册按钮 -->
    <div class="flex items-end justify-between mb-4">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">算法广场</div>
        <h1 class="text-2xl font-semibold text-ink-primary">算法管理</h1>
        <p class="text-sm text-ink-secondary mt-1">
          管理甘蔗幼苗检测模型权重 · 当前激活：<span class="text-brand-700 font-medium">{{ modelStore.currentModel || '—' }}</span>
        </p>
      </div>
      <router-link
        to="/algo/model-register"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <i class="fa-solid fa-plus text-xs"></i> 注册模型
      </router-link>
    </div>

    <SubTabs />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-5">
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">注册模型</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">{{ modelStore.models.length }}</div>
        <div class="text-xs text-ink-tertiary mt-1">全部为甘蔗幼苗检测</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">支持框架</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">2</div>
        <div class="text-xs text-ink-tertiary mt-1">Ultralytics · Custom</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">最佳 mAP@0.5</div>
        <div class="text-2xl font-semibold text-brand-700 mt-1">0.884</div>
        <div class="text-xs text-ink-tertiary mt-1">YOLO12s-sugarcane</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">推理设备</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">GPU×1</div>
        <div class="text-xs text-ink-tertiary mt-1">NVIDIA RTX 4060 Ti 16G</div>
      </div>
    </div>

    <!-- 模型表格 -->
    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-3 px-4 font-medium">模型名称</th>
            <th class="text-left py-3 px-4 font-medium">框架 / 规格</th>
            <th class="text-left py-3 px-4 font-medium">类别</th>
            <th class="text-left py-3 px-4 font-medium">推理参数</th>
            <th class="text-left py-3 px-4 font-medium">状态</th>
            <th class="text-left py-3 px-4 font-medium">更新时间</th>
            <th class="text-right py-3 px-4 font-medium w-32">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr
            v-for="m in modelStore.models"
            :key="m.name"
            class="border-t border-surface-border"
            :class="{ 'bg-brand-50/40': m.is_active }"
          >
            <td class="py-3 px-4">
              <div class="flex items-center gap-2">
                <div
                  class="w-7 h-7 rounded-btn flex items-center justify-center"
                  :class="m.is_active ? 'bg-brand-50' : 'bg-surface-bg'"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    :stroke="m.is_active ? '#10B981' : '#9CA3AF'"
                    stroke-width="1.7"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M4.6 19.6 H19.4"/>
                    <path d="M12 19.6 V11.6"/>
                    <path d="M12 13.6 C12 10.1 9.5 8.2 6.3 8.3 C6.5 11.8 9.1 13.7 12 13.6"/>
                    <path d="M12 13.6 C12 10.1 14.5 8.2 17.7 8.3 C17.5 11.8 14.9 13.7 12 13.6"/>
                  </svg>
                </div>
                <div>
                  <router-link
                    :to="`/algo/models/${m.name}`"
                    class="font-medium text-ink-primary hover:text-brand-700"
                  >
                    {{ m.display_name || m.name }}
                  </router-link>
                  <div class="text-xs text-ink-tertiary mt-0.5">{{ m.name }} · {{ m.category || '—' }}</div>
                </div>
              </div>
            </td>
            <td class="py-3 px-4">
              <div class="text-ink-primary text-xs">{{ m.engine }}</div>
              <div class="text-ink-tertiary text-xs">imgsz {{ m.imgsz }}</div>
            </td>
            <td class="py-3 px-4">
              <span class="text-xs text-ink-secondary">{{ m.category || '—' }}</span>
            </td>
            <td class="py-3 px-4">
              <div class="font-semibold text-brand-700">conf {{ m.conf }}</div>
              <div class="text-xs text-ink-tertiary">iou {{ m.iou }} · max {{ m.max_det }}</div>
            </td>
            <td class="py-3 px-4">
              <span v-if="m.is_active" class="badge badge-success">
                <span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span> 已激活
              </span>
              <span v-else class="badge badge-info">已发布</span>
            </td>
            <td class="py-3 px-4 text-xs text-ink-secondary">—</td>
            <td class="py-3 px-4 text-right">
              <div class="flex items-center justify-end gap-3">
                <router-link
                  :to="`/algo/models/${m.name}`"
                  class="text-xs text-brand-700 hover:underline"
                >详情</router-link>
                <button
                  v-if="!m.is_active"
                  class="text-xs text-brand-700 hover:underline"
                  @click="onSwitch(m)"
                >激活</button>
              </div>
            </td>
          </tr>
          <tr v-if="modelStore.models.length === 0 && !modelStore.loading">
            <td colspan="7" class="py-10 text-center text-sm text-ink-tertiary">
              <i class="fa-solid fa-folder-open text-2xl text-ink-tertiary opacity-40 mb-2 block"></i>
              暂无已注册模型，点击右上角「注册模型」添加
            </td>
          </tr>
          <tr v-if="modelStore.loading && modelStore.models.length === 0">
            <td colspan="7" class="py-10 text-center text-sm text-ink-tertiary">加载中…</td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>
