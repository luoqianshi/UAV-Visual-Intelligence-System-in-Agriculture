<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/common/Icon.vue'
import { useProcessingStore } from '@/stores/processing'
import { ref, computed, onMounted } from 'vue'
import type { ProcessingTask } from '@/api/processing'

// 按方法分组（CLAHE 增强 / 滑窗裁切）的任务表格
const store = useProcessingStore()
const tab = ref<'clahe' | 'crop'>('clahe') // 顶部子标签切换
const filterStatus = ref('') // '' | 'processing' | 'completed' | 'failed'
const errorMsg = ref('')

const groups = [
  { type: 'clahe' as const, icon: 'sparkle', title: 'CLAHE 增强', desc: '对比度受限的自适应直方图均衡化 · clipLimit 默认 2.0' },
  { type: 'crop' as const, icon: 'grid', title: '滑窗裁切', desc: '按固定尺寸滑窗裁切原图 · 默认 tile=640, overlap=0.05' },
]

function statusBadge(status: string): { cls: string; label: string } {
  if (status === 'processing') return { cls: 'badge-running', label: '进行中' }
  if (status === 'completed') return { cls: 'badge-success', label: '已完成' }
  if (status === 'failed') return { cls: 'badge-error', label: '失败' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

function typeTag(_type: string) {
  // 统一使用克制的中性标签配色（默认 .tag 样式）
  return ''
}
function typeLabel(type: string) {
  return type === 'clahe' ? 'CLAHE' : '裁切'
}

function tasksOfType(type: string): ProcessingTask[] {
  return store.tasks.filter((t) => t.task_type === type)
}

function groupStats(type: string) {
  const list = tasksOfType(type)
  const completed = list.filter((t) => t.status === 'completed').length
  const processing = list.filter((t) => t.status === 'processing').length
  return { total: list.length, completed, processing }
}

const visibleGroups = computed(() =>
  groups.filter((g) => g.type === tab.value),
)

const tabDesc = computed(() =>
  groups.find((g) => g.type === tab.value)?.desc || '',
)

function switchTab(t: 'clahe' | 'crop') {
  if (tab.value === t) return
  tab.value = t
  applyFilters()
}

async function applyFilters() {
  errorMsg.value = ''
  try {
    // 一次性拉取全部任务，tab 切换走客户端过滤（保持"累计 N 次执行"为全量）
    await store.fetchTasks({
      status: filterStatus.value || undefined,
    })
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  }
}

onMounted(applyFilters)
</script>

<template>
  <AppLayout>
    <!-- 头部 -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">数据处理</div>
        <h1 class="text-2xl font-semibold text-ink-primary">处理方法</h1>
        <p class="text-sm text-ink-secondary mt-1">{{ tabDesc }} · 累计 {{ store.taskTotal }} 次执行</p>
      </div>
      <router-link
        to="/process/task-new"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <Icon name="plus" :size="14" /> 新建任务
      </router-link>
    </div>

    <!-- 顶部子标签栏：与算法广场 / 数据管理一致 -->
    <div class="flex items-center gap-1 border-b border-surface-border mb-6">
      <button class="sub-tab" :class="{ active: tab === 'clahe' }" @click="switchTab('clahe')">
        <Icon name="sparkle" :size="14" />CLAHE 增强
      </button>
      <button class="sub-tab" :class="{ active: tab === 'crop' }" @click="switchTab('crop')">
        <Icon name="grid" :size="14" />滑窗裁切
      </button>
    </div>

    <!-- 状态筛选 -->
    <div class="bg-white border border-surface-border rounded-card p-4 mb-4">
      <div class="flex items-center gap-3">
        <span class="text-xs text-ink-tertiary">筛选：</span>
        <select v-model="filterStatus" @change="applyFilters" class="px-3 py-2 bg-white border border-surface-border rounded-btn text-sm text-ink-secondary">
          <option value="">全部状态</option>
          <option value="processing">进行中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
        </select>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="store.loading" class="bg-white border border-surface-border rounded-card py-16 text-center text-ink-tertiary">
      <Icon name="spinner" :size="24" :spin="true" class="inline-block" />
      <div class="mt-2 text-sm">加载中…</div>
    </div>
    <!-- 错误 -->
    <div v-else-if="errorMsg" class="bg-white border border-surface-border rounded-card py-16 text-center">
      <div class="text-red-600 mb-2 flex items-center justify-center gap-1.5"><Icon name="warning" :size="16" />{{ errorMsg }}</div>
      <button @click="applyFilters" class="text-brand-700 hover:underline text-xs">重试</button>
    </div>
    <!-- 空 -->
    <div v-else-if="store.tasks.length === 0" class="bg-white border border-surface-border rounded-card py-16 text-center text-ink-tertiary">
      <Icon name="folder-open" :size="32" class="mx-auto mb-2 opacity-40" />
      <div class="text-sm">暂无处理任务</div>
    </div>

    <!-- 分组表格 -->
    <div v-else class="space-y-4">
      <div
        v-for="g in visibleGroups"
        :key="g.type"
        class="bg-white border border-surface-border rounded-card overflow-hidden"
      >
        <div class="px-5 py-4 border-b border-surface-border flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-btn flex items-center justify-center bg-brand-50 text-brand-700">
              <Icon :name="g.icon" :size="18" />
            </div>
            <div>
              <h2 class="text-base font-semibold text-ink-primary">{{ g.title }}</h2>
              <p class="text-xs text-ink-tertiary mt-0.5">{{ g.desc }}</p>
            </div>
          </div>
          <div class="flex items-center gap-6 text-xs">
            <div class="text-center"><div class="text-lg font-semibold text-ink-primary">{{ groupStats(g.type).total }}</div><div class="text-ink-tertiary">执行次数</div></div>
            <div class="text-center"><div class="text-lg font-semibold text-brand-700">{{ groupStats(g.type).completed }}</div><div class="text-ink-tertiary">已完成</div></div>
            <div class="text-center"><div class="text-lg font-semibold text-ink-tertiary">{{ groupStats(g.type).processing }}</div><div class="text-ink-tertiary">进行中</div></div>
          </div>
        </div>
        <table class="w-full text-sm">
          <thead class="bg-surface-bg text-xs text-ink-secondary">
            <tr>
              <th class="text-left py-2.5 px-5 font-medium">执行编号</th>
              <th class="text-left py-2.5 px-5 font-medium">任务名</th>
              <th class="text-left py-2.5 px-5 font-medium">类型</th>
              <th class="text-left py-2.5 px-5 font-medium">输入架次</th>
              <th class="text-left py-2.5 px-5 font-medium">输出路径</th>
              <th class="text-left py-2.5 px-5 font-medium">进度</th>
              <th class="text-left py-2.5 px-5 font-medium">状态</th>
              <th class="text-left py-2.5 px-5 font-medium">创建时间</th>
              <th class="text-right py-2.5 px-5 font-medium w-20">详情</th>
            </tr>
          </thead>
          <tbody class="row-hover">
            <tr v-if="tasksOfType(g.type).length === 0">
              <td colspan="9" class="py-8 text-center text-ink-tertiary text-sm">该类型暂无任务</td>
            </tr>
            <tr
              v-for="(t, i) in tasksOfType(g.type)"
              v-else
              :key="t.task_id"
              class="border-t border-surface-border"
            >
              <td class="py-2.5 px-5 text-ink-tertiary font-mono text-xs">#{{ String(tasksOfType(g.type).length - i).padStart(3, '0') }}</td>
              <td class="py-2.5 px-5">
                <router-link :to="`/process/tasks/${t.task_id}`" class="font-medium text-ink-primary hover:text-brand-700">{{ t.name }}</router-link>
                <div class="text-xs text-ink-tertiary mt-0.5">{{ t.params?.clip_limit ? `clipLimit ${t.params.clip_limit}` : '' }}{{ t.params?.tile_size ? ` · tile ${t.params.tile_size}` : '' }}{{ t.params?.overlap_ratio ? ` · overlap ${t.params.overlap_ratio}` : '' }}</div>
              </td>
              <td class="py-2.5 px-5"><span class="tag" :class="typeTag(t.task_type)">{{ typeLabel(t.task_type) }}</span></td>
              <td class="py-2.5 px-5 text-ink-secondary text-xs">{{ t.input_paths?.[0] || '-' }}</td>
              <td class="py-2.5 px-5 text-ink-tertiary font-mono text-xs">{{ t.output_path }}</td>
              <td class="py-2.5 px-5">
                <div class="flex items-center gap-2">
                  <div class="progress w-24"><div class="progress-bar" :class="{ running: t.status === 'processing' && t.progress < 100 }" :style="{ width: t.progress + '%' }"></div></div>
                  <span class="text-xs text-ink-tertiary">{{ t.progress }}%</span>
                </div>
              </td>
              <td class="py-2.5 px-5"><span class="badge" :class="statusBadge(t.status).cls">{{ statusBadge(t.status).label }}</span></td>
              <td class="py-2.5 px-5 text-ink-secondary text-xs">{{ t.created_at }}</td>
              <td class="py-2.5 px-5 text-right">
                <router-link :to="`/process/tasks/${t.task_id}`" class="text-xs text-brand-700 hover:underline">查看</router-link>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppLayout>
</template>
