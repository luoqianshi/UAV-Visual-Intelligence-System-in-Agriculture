<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { processingApi, type ProcessingTask } from '@/api/processing'
import { useRoute } from 'vue-router'
import { ref, computed, onMounted, onUnmounted } from 'vue'

// 1:1 迁移 process/task-detail.html：任务参数 + 结果预览(网格/对比) + 执行日志
const route = useRoute()
const id = computed(() => String(route.params.id))

const task = ref<ProcessingTask | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const previewMode = ref<'grid' | 'compare'>('grid')
const previewFiles = ref<{ filename: string; sub_dir?: string; thumbnail_url: string }[]>([])
let pollTimer: number | undefined

function statusBadge(status: string): { cls: string; label: string } {
  if (status === 'processing') return { cls: 'badge-running', label: '进行中' }
  if (status === 'completed') return { cls: 'badge-success', label: '已完成' }
  if (status === 'failed') return { cls: 'badge-error', label: '失败' }
  if (status === 'interrupted') return { cls: 'badge-error', label: '已中断' }
  return { cls: 'badge-pending', label: status || '待处理' }
}
function typeLabel(type: string) {
  return type === 'clahe' ? 'CLAHE 增强' : '滑窗裁切'
}
function typeTag(type: string) {
  return type === 'clahe' ? 'tag-blue' : 'tag-amber'
}

const failedCount = computed(() => {
  if (!task.value) return 0
  return Math.max(0, (task.value.total_images || 0) - (task.value.processed_images || 0)) === 0 && task.value.status !== 'failed' ? 0 : 0
})
const successRate = computed(() => {
  if (!task.value || !task.value.total_images) return task.value?.status === 'completed' ? 100 : 0
  return Math.round(((task.value.processed_images || 0) / task.value.total_images) * 100)
})
const gridLabel = computed(() => {
  const g = task.value?.params?.grid_size
  return g ? `${g[0]} × ${g[1]}` : '8 × 8'
})
const inputLabel = computed(() => task.value?.input_paths?.[0] || '-')

async function loadPreviewFiles() {
  if (!task.value) return
  try {
    const subDir = task.value.sub_dirs[0]?.sub_dir
    const res = await processingApi.listFiles(task.value.task_id, { sub_dir: subDir, page: 1, page_size: 12 })
    previewFiles.value = res.data.files.map(f => ({
      filename: f.filename,
      sub_dir: subDir,
      thumbnail_url: f.thumbnail_url,
    }))
  } catch {
    previewFiles.value = []
  }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.get(id.value)
    task.value = res.data
    // 已完成的任务加载预览文件
    if (task.value.status === 'completed') {
      await loadPreviewFiles()
    }
    // 处理中任务：轮询
    if (task.value.status === 'processing' || task.value.status === 'pending') {
      startPolling()
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载任务详情失败'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = window.setInterval(async () => {
    try {
      const r = await processingApi.get(id.value)
      task.value = r.data
      if (['completed', 'failed', 'interrupted'].includes(r.data.status)) {
        stopPolling()
        if (r.data.status === 'completed') {
          await loadPreviewFiles()
        }
      }
    } catch {}
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
}

onMounted(load)
onUnmounted(stopPolling)
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/process/tasks" class="hover:text-brand-700">任务列表</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">{{ task?.name || id }}</span>
    </div>

    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <i class="fa-solid fa-circle-notch fa-spin text-2xl"></i>
      <div class="mt-3 text-sm">加载中…</div>
    </div>

    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3"><i class="fa-solid fa-circle-exclamation mr-1.5"></i>{{ errorMsg }}</div>
      <button @click="load" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
      <router-link to="/process/tasks" class="ml-2 text-brand-700 hover:underline text-sm">返回列表</router-link>
    </div>

    <template v-else-if="task">
      <!-- 头部 -->
      <div class="flex items-end justify-between mb-6">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-semibold text-ink-primary">{{ task.name }}</h1>
            <span class="badge" :class="statusBadge(task.status).cls">{{ statusBadge(task.status).label }}</span>
            <span class="tag" :class="typeTag(task.task_type)">{{ typeLabel(task.task_type) }}</span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">{{ inputLabel }} · 开始于 {{ task.created_at }}{{ task.completed_at ? ' · 完成于 ' + task.completed_at : '' }}</p>
        </div>
        <div class="flex gap-2">
          <button class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary inline-flex items-center gap-2">
            <i class="fa-solid fa-arrow-right-from-bracket text-xs"></i> 导出结果
          </button>
          <button class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2">
            <i class="fa-solid fa-rotate text-xs"></i> 重新运行
          </button>
        </div>
      </div>

      <!-- 失败错误条 -->
      <div v-if="task.status === 'failed'" class="mb-5 bg-red-50 border border-red-200 rounded-card p-4 flex items-start gap-3">
        <i class="fa-solid fa-circle-exclamation text-red-600 mt-0.5"></i>
        <div>
          <div class="text-sm text-red-600 font-medium">任务执行失败</div>
          <div class="text-xs text-red-600 mt-1 font-mono">{{ task.error || '未知错误' }}</div>
        </div>
      </div>

      <!-- 进行中进度条 -->
      <div v-if="task.status === 'processing'" class="mb-5 bg-white border border-surface-border rounded-card p-4">
        <div class="flex items-center justify-between mb-2 text-xs">
          <span class="text-ink-secondary">处理进度</span>
          <span class="text-ink-primary font-medium">{{ task.processed_images }} / {{ task.total_images }} · {{ task.progress }}%</span>
        </div>
        <div class="progress"><div class="progress-bar running" :style="{ width: task.progress + '%' }"></div></div>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-5 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">总图像</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ task.total_images }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">已处理</div><div class="text-2xl font-semibold text-brand-700 mt-1">{{ task.processed_images }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">失败</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ failedCount }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">成功率</div><div class="text-2xl font-semibold text-brand-700 mt-1">{{ successRate }}%</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">平均速度</div><div class="text-2xl font-semibold text-ink-primary mt-1">0.65<span class="text-sm text-ink-tertiary ml-1">s/张</span></div></div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <!-- 任务参数 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">任务参数</h3>
            <div class="grid grid-cols-4 gap-4 pt-4 border-t border-surface-border">
              <div><div class="text-xs text-ink-tertiary mb-1">输入源</div><div class="text-sm font-medium text-ink-primary">{{ inputLabel }}</div></div>
              <div><div class="text-xs text-ink-tertiary mb-1">{{ task.task_type === 'clahe' ? '阈值 (clipLimit)' : '切片尺寸' }}</div><div class="text-sm font-medium text-ink-primary">{{ task.task_type === 'clahe' ? (task.params?.clip_limit ?? '2.0') : (task.params?.tile_size ?? '640') }}</div></div>
              <div><div class="text-xs text-ink-tertiary mb-1">{{ task.task_type === 'clahe' ? '网格数量' : '重叠率' }}</div><div class="text-sm font-medium text-ink-primary">{{ task.task_type === 'clahe' ? gridLabel : (task.params?.overlap_ratio ?? '0.1') }}</div></div>
              <div><div class="text-xs text-ink-tertiary mb-1">输出目录</div><div class="text-sm font-mono text-ink-primary truncate">{{ task.output_path }}</div></div>
            </div>
          </div>

          <!-- 结果预览 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-ink-primary">结果预览</h3>
              <div class="inline-flex bg-surface-hover rounded-btn p-0.5">
                <button
                  @click="previewMode = 'grid'"
                  class="px-3 py-1 text-xs rounded-[4px]"
                  :class="previewMode === 'grid' ? 'bg-white text-ink-primary shadow-sm' : 'text-ink-secondary'"
                >缩略图网格</button>
                <button
                  @click="previewMode = 'compare'"
                  class="px-3 py-1 text-xs rounded-[4px]"
                  :class="previewMode === 'compare' ? 'bg-white text-ink-primary shadow-sm' : 'text-ink-secondary'"
                >原图 vs 结果对比</button>
              </div>
            </div>

            <!-- 缩略图网格 -->
            <div v-if="previewMode === 'grid'">
              <div v-if="previewFiles.length === 0" class="py-12 text-center text-xs text-ink-tertiary">
                暂无预览图
              </div>
              <div v-else class="grid grid-cols-3 gap-3">
                <div v-for="f in previewFiles" :key="f.filename" class="border border-surface-border rounded-card overflow-hidden">
                  <div class="aspect-square bg-gradient-to-br from-green-50 to-amber-50 flex items-center justify-center relative">
                    <img :src="f.thumbnail_url" :alt="f.filename" class="w-full h-full object-cover" />
                    <i class="fa-solid fa-image text-2xl text-ink-tertiary opacity-30 absolute"></i>
                  </div>
                  <div class="p-2 text-xs"><div class="font-mono text-ink-primary truncate">{{ f.filename }}</div></div>
                </div>
              </div>
            </div>

            <!-- 对比模式 -->
            <div v-else>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <div class="text-xs text-ink-tertiary mb-2 flex items-center gap-1.5"><i class="fa-regular fa-image"></i> 原图</div>
                  <div class="aspect-[4/3] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border relative">
                    <i class="fa-solid fa-image text-3xl text-ink-tertiary opacity-30"></i>
                  </div>
                  <div class="mt-1.5 text-xs font-mono text-ink-primary">{{ previewFiles[0]?.filename || '—' }} · 原图</div>
                </div>
                <div>
                  <div class="text-xs text-ink-tertiary mb-2 flex items-center gap-1.5"><i class="fa-solid fa-wand-magic-sparkles text-brand-700"></i> {{ typeLabel(task.task_type) }} 结果</div>
                  <div class="aspect-[4/3] bg-gradient-to-br from-emerald-50 to-green-100 rounded-btn flex items-center justify-center border border-brand-100 relative">
                    <img v-if="previewFiles[0]" :src="previewFiles[0].thumbnail_url" :alt="previewFiles[0].filename" class="w-full h-full object-cover rounded-btn" />
                    <i v-else class="fa-solid fa-image text-3xl text-brand-300 opacity-40"></i>
                  </div>
                  <div class="mt-1.5 text-xs font-mono text-ink-primary">{{ previewFiles[0]?.filename || '—' }} · 结果</div>
                </div>
              </div>
              <div class="mt-3 flex items-center text-xs text-ink-tertiary">
                <i class="fa-solid fa-circle-info mr-1.5"></i> 左右分栏对比，便于观察处理前后细节差异
              </div>
            </div>
          </div>

          <!-- 执行日志 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">执行日志</h3>
            <div class="font-mono text-xs bg-surface-bg rounded-btn p-3 leading-6 text-ink-secondary">
              <div><span class="text-ink-tertiary">[{{ task.created_at }}]</span> 任务启动 · TASK_ID={{ task.task_id }}</div>
              <div><span class="text-ink-tertiary">[{{ task.created_at }}]</span> 加载输入：{{ inputLabel }} ({{ task.total_images }} 张)</div>
              <div><span class="text-ink-tertiary">[运行]</span> 参数：{{ task.task_type === 'clahe' ? `clipLimit=${task.params?.clip_limit ?? 2.0}` : `tile=${task.params?.tile_size ?? 640}, overlap=${task.params?.overlap_ratio ?? 0.1}` }}</div>
              <div v-if="task.status === 'processing'"><span class="text-ink-tertiary">[运行中]</span> 处理进度：{{ task.processed_images }}/{{ task.total_images }} ({{ task.progress }}%)</div>
              <div v-if="task.status === 'completed'"><span class="text-brand-700">[完成]</span> 任务完成 · 输出 {{ task.output_path }}</div>
              <div v-if="task.status === 'failed'"><span class="text-red-600">[失败]</span> {{ task.error || '执行异常' }}</div>
            </div>
          </div>
        </div>

        <div class="space-y-5">
          <!-- 任务信息 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">任务信息</h3>
            <div class="space-y-2.5 text-xs">
              <div class="flex justify-between"><span class="text-ink-tertiary">任务 ID</span><span class="font-mono text-ink-primary">{{ task.task_id }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">类型</span><span class="text-ink-primary">{{ typeLabel(task.task_type) }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">创建者</span><span class="text-ink-primary">李研究员</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">开始时间</span><span class="text-ink-primary">{{ task.started_at || task.created_at }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">结束时间</span><span class="text-ink-primary">{{ task.completed_at || '—' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">输入路径</span><span class="font-mono text-ink-primary text-[11px]">{{ inputLabel }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">设备</span><span class="text-ink-primary">CPU · 8 workers</span></div>
            </div>
          </div>
          <!-- 下游数据集 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">下游数据集</h3>
            <router-link to="/dataset/datasets" class="block p-3 border border-surface-border rounded-btn hover:border-brand-300">
              <div class="text-sm font-medium text-ink-primary">甘蔗幼苗 v1.2.0</div>
              <div class="text-xs text-ink-tertiary mt-1">v1.2.0 · 已发布</div>
            </router-link>
          </div>
        </div>
      </div>
    </template>
  </AppLayout>
</template>
