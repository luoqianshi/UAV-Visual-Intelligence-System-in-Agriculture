<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, onUnmounted, ref, watchEffect } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import DetectionViewer from '@/components/algo/DetectionViewer.vue'
import { useCountingStore } from '@/stores/counting'
import { useModelStore } from '@/stores/model'
import HeatmapChart from '@/components/algo/HeatmapChart.vue'
import ConfidenceDistChart from '@/components/algo/ConfidenceDistChart.vue'
import Icon from '@/components/common/Icon.vue'

// 作物计数工作台：支持文件上传预览 + 本机路径双模式
const countingStore = useCountingStore()
const modelStore = useModelStore()

// ---- 文件上传模式状态 ----
const fileInput = ref<HTMLInputElement | null>(null)
const imgDimensions = ref<{ w: number; h: number } | null>(null)
const isDragging = ref(false)

// 原始文件由 store 持有，previewUrl 在 store.originalFile 变化时重新生成
const previewUrl = ref<string>('')
let currentObjectUrl = ''

watchEffect(() => {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl)
    currentObjectUrl = ''
  }
  if (countingStore.originalFile) {
    currentObjectUrl = URL.createObjectURL(countingStore.originalFile)
    previewUrl.value = currentObjectUrl
  } else {
    previewUrl.value = ''
  }
})

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  handleFileSelect(file)
  target.value = ''
}

function handleFileSelect(file: File) {
  imgDimensions.value = null
  imagePath.value = '' // 清空路径输入，优先使用文件上传
  countingStore.setOriginalFile(file)
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.onload = () => {
    imgDimensions.value = { w: img.naturalWidth, h: img.naturalHeight }
    URL.revokeObjectURL(url)
  }
  img.src = url
}

function clearFile() {
  countingStore.clearOriginal()
  imgDimensions.value = null
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// 拖拽事件
function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}
function onDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && file.type.startsWith('image/')) {
    handleFileSelect(file)
  }
}

// ---- 参数表单（默认值对齐原型）----
const srcMode = ref<'single' | 'dir'>('single')
const imagePath = ref('')
const modelName = ref('')
const conf = ref(0.25)
const iou = ref(0.7)
const max_det = ref(300)
const global_conf = ref(0.5)
const tile_size = ref(640)
const overlap_ratio = ref(0.05)
const nms_iou = ref(0.5)
const batch_size = ref(16)
const ground_resolution = ref(0.85)
const grid_n = ref(8)
const saveTiles = ref(false)
const enhance = ref(true)

const isRunning = computed(
  () => countingStore.status === 'pending' || countingStore.status === 'processing',
)

const canSubmit = computed(() => {
  if (isRunning.value) return false
  const hasFile = !!countingStore.originalFile
  const hasPath = !!(srcMode.value === 'single' ? imagePath.value.trim() : imagePath.value.trim())
  const hasModel = !!modelName.value
  return (hasFile || hasPath) && hasModel
})

const statusText = computed(() => {
  switch (countingStore.status) {
    case 'pending':
      return '任务已提交，等待处理…'
    case 'processing':
      return '正在执行检测与计数…'
    default:
      return ''
  }
})

// 当前激活模型的展示名（页头）
const activeModelDisplay = computed(() => {
  const m = modelStore.models.find((m) => m.name === modelStore.currentModel)
  return m?.display_name || modelStore.currentModel || '未激活'
})

// 路径 basename（输入源“已选择”提示）
const imageBasename = computed(() => {
  const p = imagePath.value.trim()
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] || p
})

// 平均置信度：从 detection_data 计算，无法计算时返回 null
const avgConfidence = computed(() => {
  const d = countingStore.result?.detection_data
  if (!d || !Array.isArray(d) || d.length === 0) return null
  let sum = 0
  let n = 0
  for (const det of d) {
    const c = det?.confidence ?? det?.score ?? det?.conf
    if (typeof c === 'number') {
      sum += c
      n++
    }
  }
  return n ? sum / n : null
})

// 热力图统计：最大/最小/标准差
const heatStats = computed(() => {
  const hm = countingStore.result?.heatmap
  if (!hm || !hm.length) return { max: 0, min: 0, std: 0 }
  const flat: number[] = []
  for (const row of hm) {
    if (Array.isArray(row)) {
      for (const v of row) if (typeof v === 'number') flat.push(v)
    }
  }
  if (!flat.length) return { max: 0, min: 0, std: 0 }
  const max = Math.max(...flat)
  const min = Math.min(...flat)
  const mean = flat.reduce((s, v) => s + v, 0) / flat.length
  const std = Math.sqrt(flat.reduce((s, v) => s + (v - mean) ** 2, 0) / flat.length)
  return { max, min, std }
})

const heatN = computed(() => countingStore.result?.params_snapshot?.grid_n || grid_n.value || 8)

// max_det 触顶告警：存在检出数达到单块上限的分块时提示密植截断风险
const maxDetWarning = computed(() => {
  const tiles = countingStore.result?.max_det_reached_tiles
  if (!tiles || tiles.length === 0) return null
  return {
    tiles,
    maxDet: countingStore.result?.params_snapshot?.max_det ?? max_det.value,
  }
})

// 相对时间
function relativeTime(iso?: string): string {
  if (!iso) return '—'
  const ts = +new Date(iso)
  if (isNaN(ts)) return '—'
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

// 历史项模型名
function historyModel(h: any): string {
  return h?.model_info?.name || h?.model_info?.display_name || h?.model_name || h?.params_snapshot?.model_name || '—'
}

function historyResultId(h: any): string {
  return h?.result_id || h?.task_id || h?._id || '—'
}

// 提交检测与计数
async function onSubmit() {
  if (isRunning.value) return
  try {
    const payload: any = {
      model_name: modelName.value || undefined,
      tile_size: tile_size.value,
      overlap_ratio: overlap_ratio.value,
      nms_iou: nms_iou.value,
      batch_size: batch_size.value,
      ground_resolution: ground_resolution.value,
      grid_n: grid_n.value,
      conf: conf.value,
      iou: iou.value,
      max_det: max_det.value,
      global_conf: global_conf.value,
      save_tiles: saveTiles.value,
      enhance: enhance.value,
    }
    if (countingStore.originalFile) {
      payload.image = countingStore.originalFile
    } else {
      payload.image_path = srcMode.value === 'single' ? imagePath.value.trim() || undefined : undefined
      payload.image_dir = srcMode.value === 'dir' ? imagePath.value.trim() || undefined : undefined
    }
    await countingStore.submit(payload)
  } catch {
    // 错误已由 store 写入 error，UI 内联展示
  }
}

// 查看历史结果：将历史项载入当前 result 以复用结果展示区
function viewHistory(h: any) {
  countingStore.stopPolling()
  countingStore.result = h
}

// 下载结果图（标注图）
function downloadAnnotated() {
  const img = countingStore.result?.annotated_image
  if (!img) return
  const a = document.createElement('a')
  a.href = img.startsWith('data:') ? img : `data:image/jpeg;base64,${img}`
  a.download = `counting_${countingStore.result?.count ?? 'result'}.jpg`
  a.click()
}

// 导出 counting_data.json（检测明细）
function downloadJson() {
  const data = countingStore.result?.detection_data
  if (!data) return
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'counting_data.json'
  a.click()
  URL.revokeObjectURL(url)
}

// 导出计数报告
function downloadReport() {
  const r = countingStore.result
  if (!r) return
  const report = {
    count: r.count,
    density_per_m2: r.density_per_m2,
    area_m2: r.area_m2,
    avg_confidence: avgConfidence.value,
    confidence_dist: r.confidence_dist,
    heatmap: r.heatmap,
    model_info: r.model_info,
    params_snapshot: r.params_snapshot,
    image_size: r.image_size,
    tile_count: r.tile_count,
    tile_results: r.tile_results,
    max_det_reached_tiles: r.max_det_reached_tiles,
    filtered_count: r.filtered_count,
    generated_at: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'counting_report.json'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  modelStore.fetchModels().finally(() => {
    if (!modelName.value && modelStore.currentModel) {
      modelName.value = modelStore.currentModel
    }
  })
  countingStore.fetchHistory().catch(() => [])
})

onBeforeUnmount(() => {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl)
    currentObjectUrl = ''
  }
})

onUnmounted(() => {
  countingStore.stopPolling()
})
</script>

<template>
  <AppLayout>
    <div class="flex items-end justify-between mb-5">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">算法广场</div>
        <h1 class="text-2xl font-bold text-ink-primary tracking-tight">作物计数</h1>
        <p class="text-sm text-ink-secondary mt-1.5">
          检测算法对原图进行检测与计数 · 甘蔗幼苗株数统计案例应用
        </p>
      </div>
      <div class="flex items-center gap-2 text-xs text-ink-tertiary">
        <span>当前激活：</span>
        <span class="text-brand-700 font-semibold">{{ activeModelDisplay }}</span>
        <router-link to="/algo/models" class="text-brand-700 hover:underline">切换</router-link>
      </div>
    </div>

    <!-- 子栏目切换 -->
    <SubTabs />

    <!-- 进度条 / 错误提示 -->
    <div v-if="isRunning || countingStore.error" class="mb-5 space-y-3">
      <div
        v-if="isRunning"
        class="bg-white border border-surface-border rounded-card p-4"
      >
        <div class="flex items-center justify-between text-xs mb-2">
          <span class="text-ink-secondary inline-flex items-center gap-1.5">
            <Icon name="spinner" :size="14" class="text-brand-700 animate-spin-slow" />
            {{ statusText }}
          </span>
          <span class="text-brand-700 font-semibold font-numeric">{{ Math.round(countingStore.progress * 100) }}%</span>
        </div>
        <div class="progress">
          <div
            class="progress-bar running"
            :style="{ width: Math.max(2, countingStore.progress * 100) + '%' }"
          ></div>
        </div>
      </div>
      <div
        v-if="countingStore.error"
        class="bg-red-50 border border-red-200 rounded-card p-3 flex items-start gap-2.5 text-sm text-red-700"
      >
        <Icon name="warning" :size="16" class="mt-0.5 flex-shrink-0" />
        <div class="flex-1">{{ countingStore.error }}</div>
      </div>
    </div>

    <div class="grid grid-cols-3 gap-5">
      <!-- 左：输入与参数 -->
      <div class="space-y-5">
        <!-- 输入源 -->
        <div class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">输入源</h3>
          <div
            class="dropzone !p-6 transition-colors"
            :class="{ '!border-brand-500 !bg-brand-50': isDragging }"
            @click="fileInput?.click()"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
          >
            <Icon name="upload" :size="36" class="text-brand-300 mb-2" />
            <div class="text-sm text-ink-primary font-medium">
              拖拽原图到此处，或点击选择
            </div>
            <div class="text-xs text-ink-tertiary mt-1">支持 JPG / PNG / BMP / TIFF · 单张 ≤50MB</div>
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              class="hidden"
              @change="onFileChange"
            />
          </div>
          <!-- 已选择文件：缩略图 + 文件名 + 大小 -->
          <div v-if="countingStore.originalFile" class="mt-3 flex items-center gap-3">
            <img
              v-if="previewUrl"
              :src="previewUrl"
              alt="预览"
              class="w-12 h-12 object-cover rounded-btn border border-surface-border flex-shrink-0"
            />
            <div class="text-xs text-ink-tertiary flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <Icon name="validate" :size="14" class="text-brand-700 flex-shrink-0" />
                <span class="text-ink-primary font-medium truncate">{{ countingStore.originalFile.name }}</span>
              </div>
              <div class="mt-0.5 font-numeric">
                {{ formatSize(countingStore.originalFile.size) }}<span v-if="imgDimensions">
                  · {{ imgDimensions.w }}×{{ imgDimensions.h }}</span
                >
              </div>
            </div>
            <button
              class="text-ink-tertiary hover:text-ink-primary flex-shrink-0 p-1 rounded hover:bg-surface-hover transition-colors"
              title="移除"
              @click="clearFile"
            >
              <Icon name="close" :size="16" />
            </button>
          </div>
          <!-- 本机路径输入（可选，用于服务器端路径模式） -->
          <div class="mt-3 pt-3 border-t border-surface-border" v-if="!countingStore.originalFile">
            <div class="flex items-center gap-4 mb-3">
              <div
                class="px-3 py-1 text-xs border-b-2 border-transparent cursor-pointer transition-colors"
                :class="
                  srcMode === 'single'
                    ? 'text-brand-700 border-brand-700 font-medium'
                    : 'text-ink-secondary hover:text-brand-700'
                "
                @click="srcMode = 'single'"
              >
                单张路径
              </div>
              <div
                class="px-3 py-1 text-xs border-b-2 border-transparent cursor-pointer transition-colors"
                :class="
                  srcMode === 'dir'
                    ? 'text-brand-700 border-brand-700 font-medium'
                    : 'text-ink-secondary hover:text-brand-700'
                "
                @click="srcMode = 'dir'"
              >
                目录路径（批量）
              </div>
            </div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">
              {{ srcMode === 'single' ? '原图本机路径（可选）' : '原图目录路径（可选）' }}
            </label>
            <input
              v-model="imagePath"
              type="text"
              :placeholder="srcMode === 'single' ? 'D:/data/sugarcane/DJI_0001.jpg' : 'D:/data/sugarcane/batch_01'"
              class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
            />
          </div>
          <div
            v-if="imageBasename && !countingStore.originalFile"
            class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5"
          >
            <Icon name="validate" :size="14" class="text-brand-700 flex-shrink-0" />
            已选择路径：<span class="text-ink-primary font-medium font-mono">{{ imageBasename }}</span>
          </div>
        </div>

        <!-- 计数参数 -->
        <div class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-4">计数参数</h3>
          <div class="space-y-3.5">
            <!-- 检测模型 -->
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">检测模型</label>
              <select
                v-model="modelName"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              >
                <option value="" disabled>请选择模型</option>
                <option v-for="m in modelStore.models" :key="m.name" :value="m.name">
                  {{ m.display_name || m.name }}{{ m.is_active ? '（激活）' : '' }}
                </option>
              </select>
            </div>

            <!-- 推理参数（单次检测） -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">conf 置信度</label>
                <input
                  v-model.number="conf"
                  type="number"
                  step="0.05"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">iou 阈值</label>
                <input
                  v-model.number="iou"
                  type="number"
                  step="0.05"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">max_det（单块上限）</label>
                <input
                  v-model.number="max_det"
                  type="number"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                />
              </div>
            </div>

            <!-- 分块检测 -->
            <div class="pt-3 border-t border-surface-border">
              <div class="text-xs font-medium text-ink-primary mb-2.5 flex items-center gap-1.5">
                <Icon name="grid" :size="14" class="text-ink-tertiary" /> 分块检测
              </div>
              <label class="flex items-start gap-2.5 cursor-pointer mb-3">
                <input
                  v-model="enhance"
                  type="checkbox"
                  class="mt-0.5 w-4 h-4 accent-brand-700 cursor-pointer"
                />
                <div class="flex-1">
                  <div class="text-xs font-medium text-ink-primary">CLAHE 预处理增强</div>
                </div>
              </label>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">tile_size</label>
                  <input
                    v-model.number="tile_size"
                    type="number"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">overlap_ratio</label>
                  <input
                    v-model.number="overlap_ratio"
                    type="number"
                    step="0.05"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">global_conf（全局二次过滤）</label>
                  <input
                    v-model.number="global_conf"
                    type="number"
                    step="0.05"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">nms_iou（全局）</label>
                  <input
                    v-model.number="nms_iou"
                    type="number"
                    step="0.05"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">batch_size（批量推理）</label>
                  <input
                    v-model.number="batch_size"
                    type="number"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
              </div>
            </div>

            <!-- 计数统计参数 -->
            <div class="pt-3 border-t border-surface-border">
              <div class="text-xs font-medium text-ink-primary mb-2.5 flex items-center gap-1.5">
                <Icon name="ruler" :size="14" class="text-ink-tertiary" /> 计数统计参数
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">地面分辨率 (cm/px)</label>
                  <input
                    v-model.number="ground_resolution"
                    type="number"
                    step="0.01"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">统计区域网格</label>
                  <input
                    v-model.number="grid_n"
                    type="number"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
              </div>
            </div>

            <!-- 调试选项 -->
            <div class="pt-3 border-t border-surface-border">
              <label class="flex items-start gap-2.5 cursor-pointer">
                <input
                  v-model="saveTiles"
                  type="checkbox"
                  class="mt-0.5 w-4 h-4 accent-brand-700 cursor-pointer"
                />
                <div class="flex-1">
                  <div class="text-xs font-medium text-ink-primary flex items-center gap-1.5">
                    <Icon name="wrench" :size="12" class="text-ink-tertiary" />
                    保存分块调试数据
                  </div>
                  <div class="text-xs text-ink-tertiary mt-0.5">
                    开启后将保存所有子块原图及检测框可视化到 results 目录，用于问题排查（会增加磁盘占用）
                  </div>
                </div>
              </label>
            </div>
          </div>

          <!-- 执行按钮 -->
          <button
            :disabled="!canSubmit"
            class="w-full mt-4 px-4 py-2.5 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            @click="onSubmit"
          >
            <Icon name="count" :size="14" />
            {{ isRunning ? '检测中…' : '执行检测与计数' }}
          </button>
        </div>
      </div>

      <!-- 右：结果展示 -->
      <div class="col-span-2 space-y-5">
        <!-- 计数总览 4 卡片 -->
        <div v-if="countingStore.result" class="grid grid-cols-4 gap-4">
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">计数总数</div>
                <div class="text-2xl font-bold text-brand-700 mt-1 font-numeric">
                  {{ countingStore.result.count ?? '—' }}
                  <span class="text-sm text-ink-tertiary font-normal">株</span>
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
                <Icon name="seedling" :size="18" />
              </div>
            </div>
          </div>
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">平均密度</div>
                <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">
                  {{ countingStore.result.density_per_m2 ?? '—' }}
                  <span class="text-sm text-ink-tertiary font-normal">株/m²</span>
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-blue-50 flex items-center justify-center text-blue-600">
                <Icon name="gauge" :size="18" />
              </div>
            </div>
          </div>
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">覆盖面积</div>
                <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">
                  {{ countingStore.result.area_m2 ?? '—' }}
                  <span class="text-sm text-ink-tertiary font-normal">m²</span>
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-amber-50 flex items-center justify-center text-amber-600">
                <Icon name="grid" :size="18" />
              </div>
            </div>
          </div>
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">平均置信度</div>
                <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">
                  {{ avgConfidence != null ? avgConfidence.toFixed(2) : '—' }}
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-purple-50 flex items-center justify-center text-purple-600">
                <Icon name="target" :size="18" />
              </div>
            </div>
          </div>
        </div>

        <!-- 检测结果图 -->
        <div v-if="countingStore.result" class="bg-white border border-surface-border rounded-card p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-ink-primary">检测结果与计数标注</h3>
            <div class="flex items-center gap-4 text-xs">
              <span class="text-ink-tertiary font-numeric">
                图像尺寸
                <span class="text-ink-primary font-semibold">
                  {{ countingStore.result.image_size ? `${countingStore.result.image_size[0]}×${countingStore.result.image_size[1]}` : '—' }}
                </span>
              </span>
              <span class="text-ink-tertiary font-numeric">
                分块数 <span class="text-ink-primary font-semibold">{{ countingStore.result.tile_count ?? '—' }}</span>
              </span>
              <span class="text-brand-700 font-semibold">计数 {{ countingStore.result.count ?? '—' }} 株</span>
            </div>
          </div>
          <!-- 分块未触发提示：tile_count=1 时说明原图未超过 tile_size -->
          <div
            v-if="countingStore.result && countingStore.result.tile_count === 1"
            class="mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-btn text-xs text-amber-700 flex items-start gap-2"
          >
            <Icon name="info" :size="14" class="mt-0.5 flex-shrink-0" />
            <div>
              本次仅生成 1 个分块：原图尺寸（{{ countingStore.result.image_size?.[0] }}×{{ countingStore.result.image_size?.[1] }}）
              未超过 tile_size（{{ countingStore.result.params_snapshot?.tile_size ?? 640 }}），整图作为单块送检，未触发滑窗分块。
              如需分块检测，请上传更大尺寸图片或调小 tile_size。
            </div>
          </div>
          <!-- max_det 触顶告警：存在检出数达到单块上限的分块 -->
          <div
            v-if="maxDetWarning"
            class="mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-btn text-xs text-amber-700 flex items-start gap-2"
          >
            <Icon name="warning" :size="14" class="mt-0.5 flex-shrink-0" />
            <div>
              <span class="font-medium">密植截断风险：</span>{{ maxDetWarning.tiles.length }} 个分块的检出数已达到
              max_det（{{ maxDetWarning.maxDet }}）上限（块索引：{{ maxDetWarning.tiles.join('、') }}），
              部分目标可能未被计入。建议调大 max_det 或调小 tile_size 后重新检测。
            </div>
          </div>
          <DetectionViewer
            :original-image="previewUrl"
            :result-image="countingStore.result?.annotated_image"
            :loading="isRunning"
            :original-empty-text="countingStore.originalFile ? '等待上传' : (imageBasename ? `原图：${imageBasename}（本机路径无法预览）` : '原图为本机路径，无法在浏览器预览')"
            result-label="检测结果（红色框 · 已计数）"
            :show-count-badge="true"
            :count="countingStore.result.count"
          />
          <div class="mt-4 flex items-center gap-2">
            <button
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 font-medium"
              @click="downloadAnnotated"
            >
              <Icon name="download" :size="12" /> 下载结果图
            </button>
            <button
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 font-medium"
              @click="downloadJson"
            >
              <Icon name="file-code" :size="12" /> 导出 counting_data.json
            </button>
            <button
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 font-medium"
              @click="downloadReport"
            >
              <Icon name="file-excel" :size="12" /> 导出计数报告
            </button>
          </div>
        </div>

        <!-- 区域分布热力统计 -->
        <div v-if="countingStore.result" class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-1">区域分布统计</h3>
          <p class="text-xs text-ink-tertiary mb-4">
            将原图按 {{ heatN }}×{{ heatN }} 网格划分，统计各区域计数分布（株/格）
          </p>
          <HeatmapChart :data="countingStore.result.heatmap" :n="heatN" />
          <div class="mt-3 text-xs text-ink-tertiary text-right font-numeric">
            最大区域 {{ heatStats.max }} 株 · 最小区域 {{ heatStats.min }} 株 · 标准差 {{ heatStats.std.toFixed(1) }}
          </div>
        </div>

        <!-- 置信度分布 -->
        <div v-if="countingStore.result" class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-4">置信度分布</h3>
          <ConfidenceDistChart :dist="countingStore.result.confidence_dist" />
        </div>

        <!-- 空状态 / 处理中提示（无结果时） -->
        <div
          v-if="!countingStore.result"
          class="bg-white border border-surface-border rounded-card p-10 text-center"
        >
          <template v-if="isRunning">
            <Icon name="spinner" :size="40" class="text-brand-300 mb-3 mx-auto animate-spin-slow" />
            <div class="text-sm text-ink-secondary">正在执行检测与计数，请稍候…</div>
          </template>
          <template v-else>
            <Icon name="count" :size="40" class="text-ink-tertiary opacity-30 mb-3 mx-auto" />
            <div class="text-sm text-ink-secondary">尚无计数结果</div>
            <div class="text-xs text-ink-tertiary mt-1">请在左侧配置输入源与参数后，点击「执行检测与计数」</div>
          </template>
        </div>

        <!-- 历史计数案例 -->
        <div class="bg-white border border-surface-border rounded-card overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border flex items-center justify-between">
            <h3 class="text-sm font-semibold text-ink-primary">历史计数案例</h3>
            <span class="text-xs text-ink-tertiary font-numeric">最近 {{ countingStore.history.length }} 条记录</span>
          </div>
          <table class="w-full text-sm">
            <thead class="bg-surface-bg text-xs text-ink-secondary">
              <tr>
                <th class="text-left py-2.5 px-5 font-medium">结果ID / 时间</th>
                <th class="text-left py-2.5 px-5 font-medium">模型</th>
                <th class="text-right py-2.5 px-5 font-medium">计数</th>
                <th class="text-right py-2.5 px-5 font-medium">密度</th>
                <th class="text-right py-2.5 px-5 font-medium">面积</th>
                <th class="text-right py-2.5 px-5 font-medium w-20">操作</th>
              </tr>
            </thead>
            <tbody class="row-hover">
              <tr
                v-for="(h, idx) in countingStore.history"
                :key="historyResultId(h) + '-' + idx"
                class="border-t border-surface-border"
                :class="{ 'bg-brand-50/30': countingStore.result && countingStore.result === h }"
              >
                <td class="py-2.5 px-5">
                  <div class="font-mono text-xs text-ink-primary truncate max-w-[180px]">
                    {{ historyResultId(h) }}
                  </div>
                  <div class="text-xs text-ink-tertiary mt-0.5">{{ relativeTime(h?.created_at) }}</div>
                </td>
                <td class="py-2.5 px-5 text-xs text-ink-secondary">{{ historyModel(h) }}</td>
                <td class="text-right py-2.5 px-5 text-brand-700 font-bold font-numeric">{{ h?.count ?? '—' }}</td>
                <td class="text-right py-2.5 px-5 text-ink-secondary text-xs font-numeric">
                  {{ h?.density_per_m2 != null ? h.density_per_m2 + ' 株/m²' : '—' }}
                </td>
                <td class="text-right py-2.5 px-5 text-ink-secondary text-xs font-numeric">
                  {{ h?.area_m2 != null ? h.area_m2 + ' m²' : '—' }}
                </td>
                <td class="text-right py-2.5 px-5">
                  <button class="text-xs text-brand-700 hover:underline font-medium" @click="viewHistory(h)">
                    查看
                  </button>
                </td>
              </tr>
              <tr v-if="countingStore.history.length === 0">
                <td colspan="6" class="py-10 text-center text-sm text-ink-tertiary">
                  <Icon name="folder-open" :size="28" class="text-ink-tertiary opacity-30 mb-2 mx-auto" />
                  暂无历史计数记录
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
