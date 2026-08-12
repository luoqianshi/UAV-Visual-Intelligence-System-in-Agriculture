<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { processingApi, type ProcessingTask, type TaskFile } from '@/api/processing'
import { useRoute } from 'vue-router'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import Icon from '@/components/common/Icon.vue'
import ImageViewer from '@/components/common/ImageViewer.vue'

// 1:1 迁移 process/task-detail.html：任务参数 + 结果预览(网格/对比) + 执行日志
const route = useRoute()
const id = computed(() => String(route.params.id))

const task = ref<ProcessingTask | null>(null)
const loading = ref(true)
const errorMsg = ref('')

// 数据：每个 sub_dir 的文件列表（用于"取第一张原图"和 Crop 的 tile 渲染）
const filesBySubDir = ref<Record<string, TaskFile[]>>({})
const currentSubDir = ref<string>('')
const tileFiles = ref<TaskFile[]>([])

// 大图弹窗
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')

function openViewer(src: string, alt: string) {
  if (!src) return
  viewerSrc.value = src
  viewerAlt.value = alt
  viewerVisible.value = true
}

function previewUrl(filename: string, subDir?: string, size: 'thumbnail' | 'medium' | 'original' = 'medium'): string {
  if (!task.value) return ''
  return processingApi.previewUrl(task.value.task_id, filename, subDir, size)
}

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

const successRate = computed(() => {
  if (!task.value || !task.value.total_images) return task.value?.status === 'completed' ? 100 : 0
  return Math.round(((task.value.processed_images || 0) / task.value.total_images) * 100)
})
const gridLabel = computed(() => {
  const g = task.value?.params?.grid_size
  return g ? `${g[0]} × ${g[1]}` : '8 × 8'
})
const inputLabel = computed(() => task.value?.input_paths?.[0] || '-')
const isClahe = computed(() => task.value?.task_type === 'clahe')
const isCrop = computed(() => task.value?.task_type === 'crop')

// CLAHE：第一张文件（来自第一个 sub_dir）
const firstSubDir = computed(() => task.value?.sub_dirs?.[0]?.sub_dir || '')
const firstClaheFile = computed<TaskFile | null>(() => {
  const files = filesBySubDir.value[firstSubDir.value] || []
  return files[0] || null
})

// Crop：第一张原图（文件名去掉 _tile_xxxx_x*_y* 后缀） + 该原图对应的所有 tile
// 注意：原图本身不在 output 目录中（output 只有 tile），所以我们用第一张 tile（_tile_0001_x0_y0）
// 作为"第一张图片的可视化"来展示，并展示该原图对应的所有 tile 网格
const firstCropOrigStem = computed(() => {
  const files = filesBySubDir.value[firstSubDir.value] || []
  for (const f of files) {
    // tiling 命名: {stem}_tile_0001_x0_y0.jpg
    const m = f.filename.match(/^(.+?)_tile_\d{4}_x\d+_y\d+\.jpg$/)
    if (m) return m[1]
  }
  return null
})
// 第一张 tile（最左上角的 tile_0001_x0_y0）作为"第一张图片"的代理预览
const firstCropTile = computed<TaskFile | null>(() => {
  if (!firstCropOrigStem.value) return null
  const files = filesBySubDir.value[firstSubDir.value] || []
  const target = `${firstCropOrigStem.value}_tile_0001_x0_y0.jpg`
  return files.find((f) => f.filename.toLowerCase() === target) || null
})

async function loadAllFilesForFirstSubDir() {
  if (!task.value || !firstSubDir.value) return
  try {
    // CLAHE：拿第一张即可（避免大列表），但仍请求 1 条以校验存在
    // Crop：拿全部 tile（第一页前 200 张应该足够覆盖 80 张原图 × 50 tile = 4000）
    const pageSize = isCrop.value ? 200 : 1
    const res = await processingApi.listFiles(task.value.task_id, {
      sub_dir: firstSubDir.value,
      page: 1,
      page_size: pageSize,
    })
    filesBySubDir.value[firstSubDir.value] = res.data.files
    if (isCrop.value && firstCropOrigStem.value) {
      // 用 filename_prefix 过滤出该原图对应的所有 tile
      const tileRes = await processingApi.listFiles(task.value.task_id, {
        sub_dir: firstSubDir.value,
        filename_prefix: `${firstCropOrigStem.value}_tile_`,
        page: 1,
        page_size: 200,
      })
      tileFiles.value = tileRes.data.files
    }
  } catch {
    filesBySubDir.value[firstSubDir.value] = []
    tileFiles.value = []
  }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.get(id.value)
    task.value = res.data
    if (task.value.status === 'completed') {
      await loadAllFilesForFirstSubDir()
    }
    if (task.value.status === 'processing' || task.value.status === 'pending') {
      startPolling()
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载任务详情失败'
  } finally {
    loading.value = false
  }
}

let pollTimer: number | undefined
function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = window.setInterval(async () => {
    try {
      const r = await processingApi.get(id.value)
      task.value = r.data
      if (['completed', 'failed', 'interrupted'].includes(r.data.status)) {
        stopPolling()
        if (r.data.status === 'completed') {
          await loadAllFilesForFirstSubDir()
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
      <Icon name="chevron-right" :size="10" />
      <span class="text-ink-primary">{{ task?.name || id }}</span>
    </div>

    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <Icon name="spinner" :size="24" :spin="true" class="inline mr-2" /> 加载中…
    </div>

    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3"><Icon name="warning" :size="16" class="inline mr-1.5" />{{ errorMsg }}</div>
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
            <Icon name="export" :size="14" /> 导出结果
          </button>
          <button class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2">
            <Icon name="spinner" :size="14" /> 重新运行
          </button>
        </div>
      </div>

      <!-- 失败错误条 -->
      <div v-if="task.status === 'failed'" class="mb-5 bg-red-50 border border-red-200 rounded-card p-4 flex items-start gap-3">
        <Icon name="warning" :size="16" class="text-red-600 mt-0.5" />
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
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">失败</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ Math.max(0, (task.total_images || 0) - (task.processed_images || 0)) }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">成功率</div><div class="text-2xl font-semibold text-brand-700 mt-1">{{ successRate }}%</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">{{ isCrop ? '子图总数' : '平均速度' }}</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            <template v-if="isCrop">{{ task.total_tiles ?? 0 }}<span class="text-sm text-ink-tertiary ml-1">tiles</span></template>
            <template v-else>0.65<span class="text-sm text-ink-tertiary ml-1">s/张</span></template>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <!-- 任务参数 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">任务参数</h3>
            <div class="grid grid-cols-4 gap-4 pt-4 border-t border-surface-border">
              <div><div class="text-xs text-ink-tertiary mb-1">输入源</div><div class="text-sm font-medium text-ink-primary">{{ inputLabel }}</div></div>
              <div><div class="text-xs text-ink-tertiary mb-1">{{ isClahe ? '阈值 (clipLimit)' : '切片尺寸' }}</div><div class="text-sm font-medium text-ink-primary">{{ isClahe ? (task.params?.clip_limit ?? '2.0') : (task.params?.tile_size ?? '640') }}</div></div>
              <div><div class="text-xs text-ink-tertiary mb-1">{{ isClahe ? '网格数量' : '重叠率' }}</div><div class="text-sm font-medium text-ink-primary">{{ isClahe ? gridLabel : (task.params?.overlap_ratio ?? '0.05') }}</div></div>
              <div><div class="text-xs text-ink-tertiary mb-1">输出目录</div><div class="text-sm font-mono text-ink-primary truncate">{{ task.output_path }}</div></div>
            </div>
          </div>

          <!-- 快速预览（按方法差异化） -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-ink-primary">快速预览</h3>
              <span class="text-xs text-ink-tertiary">
                <template v-if="isClahe">第一张图片 · 增强前后对比</template>
                <template v-else-if="isCrop">第一张原图 · 滑窗分块结果</template>
              </span>
            </div>

            <!-- CLAHE：原图 vs 增强后单图对比 -->
            <div v-if="isClahe">
              <div v-if="!firstClaheFile" class="py-12 text-center text-xs text-ink-tertiary">
                暂无预览图
              </div>
              <div v-else class="grid grid-cols-2 gap-4">
                <div>
                  <div class="text-xs text-ink-tertiary mb-2 flex items-center gap-1.5">
                    <Icon name="image" :size="12" /> 原图
                    <span class="ml-auto text-[10px] text-brand-700/70 inline-flex items-center gap-1">
                      <Icon name="search" :size="10" /> 点击放大
                    </span>
                  </div>
                  <div
                    class="aspect-[4/3] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border overflow-hidden cursor-zoom-in group relative"
                    @click="openViewer(previewUrl(firstClaheFile.filename, firstSubDir, 'original'), firstClaheFile.filename + ' · 原图')"
                  >
                    <img :src="previewUrl(firstClaheFile.filename, firstSubDir, 'medium')" :alt="firstClaheFile.filename" class="w-full h-full object-contain transition-transform duration-200 group-hover:scale-[1.02]" />
                  </div>
                  <div class="mt-1.5 text-xs font-mono text-ink-primary truncate">{{ firstClaheFile.filename }}</div>
                </div>
                <div>
                  <div class="text-xs text-ink-tertiary mb-2 flex items-center gap-1.5">
                    <Icon name="sparkle" :size="12" class="text-brand-700" /> CLAHE 增强后
                    <span class="ml-auto text-[10px] text-brand-700/70 inline-flex items-center gap-1">
                      <Icon name="search" :size="10" /> 点击放大
                    </span>
                  </div>
                  <div
                    class="aspect-[4/3] bg-gradient-to-br from-emerald-50 to-green-100 rounded-btn flex items-center justify-center border border-brand-100 overflow-hidden cursor-zoom-in group relative"
                    @click="openViewer(previewUrl(firstClaheFile.filename, firstSubDir, 'original'), firstClaheFile.filename + ' · CLAHE')"
                  >
                    <img :src="previewUrl(firstClaheFile.filename, firstSubDir, 'medium')" :alt="firstClaheFile.filename" class="w-full h-full object-contain transition-transform duration-200 group-hover:scale-[1.02]" />
                  </div>
                  <div class="mt-1.5 text-xs font-mono text-ink-primary truncate">{{ firstClaheFile.filename }}</div>
                </div>
              </div>
              <div class="mt-3 flex items-center text-xs text-ink-tertiary">
                <Icon name="info" :size="12" class="mr-1.5" /> 同一文件名左为原图、右为增强后；输出目录为 <code class="px-1 py-0.5 bg-surface-hover rounded">{{ task.output_path }}</code>
              </div>
            </div>

            <!-- Crop：第一张 tile（代理预览） + 该原图对应的所有 tile 网格 -->
            <div v-else-if="isCrop">
              <div v-if="!firstCropTile && tileFiles.length === 0" class="py-12 text-center text-xs text-ink-tertiary">
                暂无预览图
              </div>
              <template v-else>
                <!-- 第一张 tile（可视作第一张图片的左上角分块） -->
                <div v-if="firstCropTile" class="mb-4">
                  <div class="text-xs text-ink-tertiary mb-2 flex items-center gap-1.5">
                    <Icon name="image" :size="12" /> 第一张图片 · 左上角分块预览
                    <span class="ml-auto text-[10px] text-brand-700/70 inline-flex items-center gap-1">
                      <Icon name="search" :size="10" /> 点击放大
                    </span>
                  </div>
                  <div
                    class="aspect-[16/9] bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center border border-surface-border overflow-hidden cursor-zoom-in group relative"
                    @click="openViewer(previewUrl(firstCropTile.filename, firstSubDir, 'original'), firstCropTile.filename)"
                  >
                    <img :src="previewUrl(firstCropTile.filename, firstSubDir, 'medium')" :alt="firstCropTile.filename" class="w-full h-full object-contain transition-transform duration-200 group-hover:scale-[1.02]" />
                  </div>
                  <div class="mt-1.5 text-xs font-mono text-ink-primary truncate">{{ firstCropTile.filename }}</div>
                </div>

                <!-- Tile 缩略图网格 -->
                <div>
                  <div class="text-xs text-ink-tertiary mb-2 flex items-center gap-1.5">
                    <Icon name="grid" :size="12" /> 分块缩略图
                    <span class="text-ink-tertiary">（{{ tileFiles.length }} 张 · 对应原图 stem: <code class="px-1 bg-surface-hover rounded">{{ firstCropOrigStem || '—' }}</code>）</span>
                    <span class="ml-auto text-[10px] text-brand-700/70 inline-flex items-center gap-1">
                      <Icon name="search" :size="10" /> 单击放大
                    </span>
                  </div>
                  <div v-if="tileFiles.length === 0" class="py-8 text-center text-xs text-ink-tertiary">未找到对应 tile</div>
                  <div v-else class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                    <div
                      v-for="t in tileFiles"
                      :key="t.filename"
                      class="border border-surface-border rounded-btn overflow-hidden cursor-zoom-in group relative"
                      @click="openViewer(previewUrl(t.filename, firstSubDir, 'original'), t.filename)"
                    >
                      <div class="aspect-square bg-gradient-to-br from-green-50 to-amber-50">
                        <img :src="previewUrl(t.filename, firstSubDir, 'thumbnail')" :alt="t.filename" class="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105" loading="lazy" />
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- 执行日志 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">执行日志</h3>
            <div class="font-mono text-xs bg-surface-bg rounded-btn p-3 leading-6 text-ink-secondary">
              <div><span class="text-ink-tertiary">[{{ task.created_at }}]</span> 任务启动 · TASK_ID={{ task.task_id }}</div>
              <div><span class="text-ink-tertiary">[{{ task.created_at }}]</span> 加载输入：{{ inputLabel }} ({{ task.total_images }} 张)</div>
              <div><span class="text-ink-tertiary">[运行]</span> 参数：{{ isClahe ? `clipLimit=${task.params?.clip_limit ?? 2.0}` : `tile=${task.params?.tile_size ?? 640}, overlap=${task.params?.overlap_ratio ?? 0.05}` }}</div>
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
              <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">输入路径</span><span class="font-mono text-ink-primary text-[11px] text-right break-all">{{ inputLabel }}</span></div>
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

      <!-- 大图弹窗 -->
      <ImageViewer v-model:visible="viewerVisible" :src="viewerSrc" :alt="viewerAlt" />
    </template>
  </AppLayout>
</template>
