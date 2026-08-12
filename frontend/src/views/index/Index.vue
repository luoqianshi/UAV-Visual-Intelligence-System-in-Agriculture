<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/common/Icon.vue'
import { useMockStore } from '@/stores/mock'
import { useProcessingStore } from '@/stores/processing'
import { useCountingStore } from '@/stores/counting'
import { useModelStore } from '@/stores/model'
import { batchesApi } from '@/api/batches'

const mockStore = useMockStore()
const processingStore = useProcessingStore()
const countingStore = useCountingStore()
const modelStore = useModelStore()

// 架次数据（真实 API）
const batchCount = ref(0)
const batchTotalImages = ref(0)
const totalImages = computed(() => batchTotalImages.value)
const processingCount = computed(
  () => processingStore.tasks.filter((t) => t.status === 'processing').length,
)
const totalSamples = computed(() =>
  mockStore.datasets.reduce((s, d) => s + (d.sample_count || 0), 0),
)
const activeModelDisplay = computed(() => {
  const m = modelStore.models.find((m) => m.name === modelStore.currentModel)
  return m?.display_name || modelStore.currentModel || '未激活'
})

// 最近活动：处理任务（top 3）+ 计数历史（top 2），按时间倒序取 4 条
interface ActivityItem {
  badge: string
  badgeClass: string
  text: string
  time: string
  to: string
}

function relativeTime(iso?: string): string {
  if (!iso) return ''
  const ts = +new Date(iso)
  if (isNaN(ts)) return ''
  const diff = Math.max(0, Date.now() - ts)
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day === 1) return '昨天'
  if (day < 30) return `${day} 天前`
  const mo = Math.floor(day / 30)
  if (mo < 12) return `${mo} 个月前`
  return `${Math.floor(mo / 12)} 年前`
}

const activities = computed<ActivityItem[]>(() => {
  const raw: Array<ActivityItem & { ts: number }> = []

  for (const t of processingStore.tasks) {
    const ts = +new Date(t.created_at)
    if (isNaN(ts)) continue
    const time = relativeTime(t.created_at)
    if (t.status === 'processing') {
      raw.push({
        badge: '处理',
        badgeClass: 'badge-running',
        text: t.name,
        time: `${time} · ${Math.round(t.progress || 0)}%`,
        to: `/process/tasks/${t.task_id}`,
        ts,
      })
    } else if (t.status === 'completed') {
      raw.push({
        badge: '处理',
        badgeClass: 'badge-success',
        text: `${t.name} 已完成 · ${t.total_images ?? 0} 张`,
        time,
        to: `/process/tasks/${t.task_id}`,
        ts,
      })
    } else {
      raw.push({
        badge: '处理',
        badgeClass: 'badge-error',
        text: `${t.name} 失败`,
        time,
        to: `/process/tasks/${t.task_id}`,
        ts,
      })
    }
  }

  for (const h of countingStore.history || []) {
    const ts = +new Date(h?.created_at)
    if (isNaN(ts)) continue
    const count = h?.count ?? h?.result?.count
    raw.push({
      badge: '计数',
      badgeClass: 'badge-info',
      text: count != null ? `计数完成 · ${count} 株` : '计数任务完成',
      time: relativeTime(h?.created_at),
      to: '/algo/counting',
      ts,
    })
  }

  return raw.sort((a, b) => b.ts - a.ts).slice(0, 4)
})

onMounted(() => {
  Promise.all([
    batchesApi.list().then((res) => {
      batchCount.value = res.data.summary.total_batches
      batchTotalImages.value = res.data.summary.total_images
    }).catch(() => {}),
    processingStore.fetchTasks(),
    mockStore.fetchDatasets(),
    modelStore.fetchModels(),
    countingStore.fetchHistory().catch(() => []),
  ])
})
</script>

<template>
  <AppLayout>
    <!-- 页头 -->
    <div class="mb-6">
      <div class="text-xs text-ink-tertiary mb-1">工作台</div>
      <h1 class="text-2xl font-semibold text-ink-primary">田间智监 · 端到端工作流</h1>
      <p class="text-sm text-ink-secondary mt-1">
        基于无人机图像的大田农作物智能监测 · 数据 → 处理 → 数据集 → 算法 四模块闭环
      </p>
    </div>

    <!-- 端到端流程 -->
    <div class="bg-white border border-surface-border rounded-card p-5 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-semibold text-ink-primary">端到端流程</h2>
        <span class="text-xs text-ink-tertiary">纯像素流程 · 本地部署</span>
      </div>
      <div class="grid grid-cols-4 gap-3">
        <!-- 阶段 1 数据管理 -->
        <router-link
          to="/data/batches"
          class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition"
        >
          <div class="flex items-center gap-2 mb-2">
            <div class="w-8 h-8 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
              <Icon name="dataset" :size="16" />
            </div>
            <div class="text-xs text-ink-tertiary">阶段 1</div>
          </div>
          <div class="text-sm font-semibold text-ink-primary">数据管理</div>
          <div class="text-xs text-ink-tertiary mt-1">按架次登记 UAV 原始图片，本机路径浏览</div>
          <div class="text-xs text-brand-700 mt-2 font-medium">
            {{ totalImages }} 张原图 · {{ batchCount }} 架次
          </div>
        </router-link>

        <!-- 阶段 2 数据处理 -->
        <router-link
          to="/process/tasks"
          class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition"
        >
          <div class="flex items-center gap-2 mb-2">
            <div class="w-8 h-8 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
              <Icon name="augment" :size="16" />
            </div>
            <div class="text-xs text-ink-tertiary">阶段 2</div>
          </div>
          <div class="text-sm font-semibold text-ink-primary">数据处理</div>
          <div class="text-xs text-ink-tertiary mt-1">CLAHE 增强、滑窗裁切，产出待标注数据集</div>
          <div class="text-xs text-brand-700 mt-2 font-medium">
            {{ processingStore.taskTotal }} 次执行 · {{ processingCount }} 进行中
          </div>
        </router-link>

        <!-- 阶段 3 数据集管理 -->
        <router-link
          to="/dataset/datasets"
          class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition"
        >
          <div class="flex items-center gap-2 mb-2">
            <div class="w-8 h-8 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
              <Icon name="database" :size="16" />
            </div>
            <div class="text-xs text-ink-tertiary">阶段 3</div>
          </div>
          <div class="text-sm font-semibold text-ink-primary">数据集管理</div>
          <div class="text-xs text-ink-tertiary mt-1">消费外部标注，拆分构建与多格式导出</div>
          <div class="text-xs text-brand-700 mt-2 font-medium">
            {{ mockStore.datasetTotal }} 个数据集 · {{ totalSamples.toLocaleString() }} 样本
          </div>
        </router-link>

        <!-- 阶段 4 算法广场 -->
        <router-link
          to="/algo/models"
          class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition"
        >
          <div class="flex items-center gap-2 mb-2">
            <div class="w-8 h-8 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
              <Icon name="chip" :size="16" />
            </div>
            <div class="text-xs text-ink-tertiary">阶段 4</div>
          </div>
          <div class="text-sm font-semibold text-ink-primary">算法广场</div>
          <div class="text-xs text-ink-tertiary mt-1">模型注册、热切换与单图/批量检测推理</div>
          <div class="text-xs text-brand-700 mt-2 font-medium">
            {{ modelStore.models.length }} 个模型 · 激活 {{ activeModelDisplay }}
          </div>
        </router-link>
      </div>
      <div
        class="mt-4 pt-3 border-t border-surface-border text-xs text-ink-tertiary flex items-center gap-1.5"
      >
        <Icon name="info" :size="13" />
        阶段 2 产出的处理结果交付外部标注工具标注后，作为阶段 3 的标注输入；阶段 4 直接对图片执行检测推理。
      </div>
    </div>

    <!-- 快速入口（左） + 最近活动（右） -->
    <div class="grid grid-cols-3 gap-5">
      <div class="col-span-2 space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-sm font-semibold text-ink-primary">快速入口</h2>
            <span class="text-xs text-ink-tertiary">常用操作直达</span>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <router-link
              to="/data/batch-new"
              class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition flex items-start gap-3"
            >
              <div
                class="w-10 h-10 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700 flex-shrink-0"
              >
                <Icon name="dataset" :size="18" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-ink-primary">登记新架次</div>
                <div class="text-xs text-ink-tertiary mt-0.5">登记 UAV 采集参数与本机图片路径</div>
              </div>
            </router-link>
            <router-link
              to="/process/task-new"
              class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition flex items-start gap-3"
            >
              <div
                class="w-10 h-10 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700 flex-shrink-0"
              >
                <Icon name="augment" :size="18" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-ink-primary">新建处理任务</div>
                <div class="text-xs text-ink-tertiary mt-0.5">CLAHE 增强 / 滑窗裁切</div>
              </div>
            </router-link>
            <router-link
              to="/dataset/dataset-new"
              class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition flex items-start gap-3"
            >
              <div
                class="w-10 h-10 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700 flex-shrink-0"
              >
                <Icon name="database" :size="18" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-ink-primary">构建数据集</div>
                <div class="text-xs text-ink-tertiary mt-0.5">拆分 train/val/test 与多格式导出</div>
              </div>
            </router-link>
            <router-link
              to="/algo/detect"
              class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition flex items-start gap-3"
            >
              <div
                class="w-10 h-10 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700 flex-shrink-0"
              >
                <Icon name="bolt" :size="18" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-ink-primary">检测工作台</div>
                <div class="text-xs text-ink-tertiary mt-0.5">单图 / 批量检测推理</div>
              </div>
            </router-link>
            <router-link
              to="/algo/counting"
              class="border border-surface-border rounded-card p-4 hover:border-brand-300 hover:bg-brand-50/30 transition flex items-start gap-3"
            >
              <div
                class="w-10 h-10 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700 flex-shrink-0"
              >
                <Icon name="count" :size="18" />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-ink-primary">计数工作台</div>
                <div class="text-xs text-ink-tertiary mt-0.5">单图 / 批量作物计数</div>
              </div>
            </router-link>
          </div>
        </div>
      </div>

      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5">
          <h2 class="text-sm font-semibold text-ink-primary mb-4">最近活动</h2>
          <div v-if="activities.length" class="space-y-2 text-xs">
            <router-link
              v-for="(item, idx) in activities"
              :key="idx"
              :to="item.to"
              class="flex items-center gap-3 p-2.5 hover:bg-surface-hover rounded-btn"
            >
              <span class="badge" :class="item.badgeClass">{{ item.badge }}</span>
              <span class="text-ink-primary flex-1">{{ item.text }}</span>
              <span class="text-ink-tertiary">{{ item.time }}</span>
            </router-link>
          </div>
          <div v-else class="text-xs text-ink-tertiary text-center py-8 flex items-center justify-center gap-1.5">
            <Icon name="bell" :size="14" /> 暂无最近活动
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
