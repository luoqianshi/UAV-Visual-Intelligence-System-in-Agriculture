<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import ImageViewer from '@/components/common/ImageViewer.vue'
import { datasetsApi, type Dataset, type DatasetReport, type DatasetImage } from '@/api/datasets'
import { useRoute, useRouter } from 'vue-router'
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const dataset = ref<Dataset | null>(null)
const report = ref<DatasetReport | null>(null)
const reportLoading = ref(false)
const reportError = ref('')
const loading = ref(true)
const errorMsg = ref('')

// 样本浏览
const currentSplit = ref<'train' | 'val' | 'test'>('train')
const images = ref<DatasetImage[]>([])
const imagesTotal = ref(0)
const imagesPage = ref(1)
const imagesPageSize = 50
const imagesTotalPages = ref(1)
const viewerImage = ref<string>('')
const viewerVisible = ref(false)
const viewerAlt = ref('')

// ECharts 容器引用
const classChartRef = ref<HTMLElement | null>(null)
const areaChartRef = ref<HTMLElement | null>(null)
const sizeChartRef = ref<HTMLElement | null>(null)
let classChart: echarts.ECharts | null = null
let areaChart: echarts.ECharts | null = null
let sizeChart: echarts.ECharts | null = null

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('ready')) return { cls: 'badge-success', label: '已就绪' }
  if (s.includes('build')) return { cls: 'badge-running', label: '构建中' }
  if (s.includes('fail')) return { cls: 'badge-pending', label: '失败' }
  return { cls: 'badge-info', label: status || '—' }
}
function formatTagStyle(fmt: string) {
  if (fmt === 'YOLO') return { cls: 'tag tag-blue', style: '' }
  if (fmt === 'COCO') return { cls: 'tag', style: 'background:#FEF3C7;color:#B45309;' }
  if (fmt === 'VOC') return { cls: 'tag', style: 'background:#F3E8FF;color:#7E22CE;' }
  return { cls: 'tag', style: '' }
}
function formatLabel(fmt: string) {
  return fmt === 'VOC' ? 'Pascal VOC' : fmt
}
function sourceLabel(s: string) {
  return s === 'built' ? '构建' : '导入'
}

// 目录树（按格式示意）
const tree = computed(() => {
  const d = dataset.value
  if (!d) return [] as { depth: number; icon: string; iconColor: string; name: string; note?: string }[]
  const root = d.path || `${d.name}/`
  if (d.format === 'YOLO') {
    return [
      { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'images/' },
      { depth: 2, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'train/', note: `${d.train_count} 张` },
      { depth: 2, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'val/', note: `${d.val_count} 张` },
      { depth: 2, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'test/', note: `${d.test_count || 0} 张` },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'labels/', note: 'YOLO .txt 标注' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-blue-600', name: 'data.yaml', note: 'YOLO 配置' },
      { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
    ]
  }
  if (d.format === 'COCO') {
    return [
      { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'train/', note: `${d.train_count} 张` },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'val/', note: `${d.val_count} 张` },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'test/', note: `${d.test_count || 0} 张` },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'annotations/', note: 'COCO .json 标注' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'train.json' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'val.json' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'test.json' },
      { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
    ]
  }
  // VOC
  return [
    { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'train/images/', note: `${d.train_count} 张` },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'val/images/', note: `${d.val_count} 张` },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'test/images/', note: `${d.test_count || 0} 张` },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: '*/annotations/', note: 'VOC .xml 标注' },
    { depth: 1, icon: 'fa-file-lines', iconColor: 'text-green-600', name: 'voc_classes.txt' },
    { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
    { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
  ]
})

// 数据划分摘要（兼容字段 train_count/val_count/test_count/sample_count 已由 normalize 映射）
const summaryRows = computed(() => {
  const d = dataset.value
  if (!d) return []
  return [
    { set: 'train', color: 'text-brand-700', images: d.train_count, pct: d.sample_count ? ((d.train_count / d.sample_count) * 100).toFixed(1) : '—' },
    { set: 'val', color: 'text-brand-300', images: d.val_count, pct: d.sample_count ? ((d.val_count / d.sample_count) * 100).toFixed(1) : '—' },
    { set: 'test', color: 'text-brand-100', images: d.test_count || 0, pct: d.sample_count ? (((d.test_count || 0) / d.sample_count) * 100).toFixed(1) : '—' },
  ]
})
const splitRatioLabel = computed(() => {
  const d = dataset.value
  if (!d) return '—'
  if (!d.test_count) return `${d.train_count} : ${d.val_count}`
  return `${d.train_count} : ${d.val_count} : ${d.test_count}`
})

async function loadDataset() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await datasetsApi.fetchDataset(id.value)
    dataset.value = res.data
    await loadReport()
    await loadImages()
  } catch (e: any) {
    errorMsg.value = e.message || '加载数据集详情失败'
  } finally {
    loading.value = false
  }
}

async function loadReport(force = false) {
  reportLoading.value = true
  reportError.value = ''
  try {
    const res = await datasetsApi.fetchReport(id.value, force)
    report.value = res.data
    await nextTick()
    renderCharts()
  } catch (e: any) {
    reportError.value = e.response?.data?.message || e.message || '报告未生成'
  } finally {
    reportLoading.value = false
  }
}

function renderCharts() {
  const r = report.value
  if (!r) return
  // 1. 类别分布柱状图
  if (classChartRef.value) {
    classChart?.dispose()
    classChart = echarts.init(classChartRef.value)
    classChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 48, right: 16, top: 16, bottom: 56 },
      xAxis: {
        type: 'category',
        data: r.class_dist.map(c => c.name),
        axisLabel: { color: '#787774', fontSize: 11, interval: 0, rotate: r.class_dist.length > 6 ? 30 : 0 },
        axisLine: { lineStyle: { color: '#E9E9E7' } },
        axisTick: { show: false },
      },
      yAxis: { type: 'value', axisLine: { show: false }, axisLabel: { color: '#9B9A97', fontSize: 10 }, splitLine: { lineStyle: { color: '#F0F0EE' } } },
      series: [{
        type: 'bar',
        data: r.class_dist.map(c => c.count),
        itemStyle: { color: '#10B981', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 48,
      }],
    })
  }
  // 2. bbox 面积分布直方图
  if (areaChartRef.value) {
    areaChart?.dispose()
    areaChart = echarts.init(areaChartRef.value)
    const hist = r.bbox_stats.area_hist || []
    areaChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (p: any) => {
          const item = p[0]
          const bounds = hist[item.dataIndex]?.[0] || []
          return `面积区间 [${bounds[0]} ~ ${bounds[1]}]<br/>目标数：${item.value}`
        },
      },
      grid: { left: 48, right: 16, top: 16, bottom: 64 },
      xAxis: {
        type: 'category',
        data: hist.map(h => `${h[0][0]}~${h[0][1]}`),
        axisLabel: { rotate: 45, fontSize: 9, color: '#9B9A97' },
        axisLine: { lineStyle: { color: '#E9E9E7' } },
        axisTick: { show: false },
      },
      yAxis: { type: 'value', axisLine: { show: false }, axisLabel: { color: '#9B9A97', fontSize: 10 }, splitLine: { lineStyle: { color: '#F0F0EE' } } },
      series: [{
        type: 'bar',
        data: hist.map(h => h[1]),
        itemStyle: { color: '#10B981', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 28,
      }],
    })
  }
  // 3. small/medium/large 尺度堆叠条
  if (sizeChartRef.value) {
    sizeChart?.dispose()
    sizeChart = echarts.init(sizeChartRef.value)
    const sd = r.bbox_stats.size_dist
    sizeChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (p: any) => p.map((i: any) => `${i.seriesName}：${(i.value * 100).toFixed(1)}%`).join('<br/>') },
      legend: { bottom: 0, textStyle: { color: '#787774', fontSize: 11 }, itemWidth: 12, itemHeight: 12 },
      grid: { left: 48, right: 16, top: 16, bottom: 40 },
      xAxis: { type: 'category', data: ['目标尺度分布'], axisLine: { lineStyle: { color: '#E9E9E7' } }, axisTick: { show: false }, axisLabel: { color: '#787774', fontSize: 11 } },
      yAxis: { type: 'value', max: 1, axisLine: { show: false }, axisLabel: { color: '#9B9A97', fontSize: 10, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: '#F0F0EE' } } },
      series: [
        { name: 'small (<32²)', type: 'bar', stack: 'size', data: [sd.small], itemStyle: { color: '#FBBF24' }, barMaxWidth: 80 },
        { name: 'medium (32²~96²)', type: 'bar', stack: 'size', data: [sd.medium], itemStyle: { color: '#10B981' }, barMaxWidth: 80 },
        { name: 'large (>96²)', type: 'bar', stack: 'size', data: [sd.large], itemStyle: { color: '#3B82F6' }, barMaxWidth: 80 },
      ],
    })
  }
}

function resizeCharts() {
  classChart?.resize()
  areaChart?.resize()
  sizeChart?.resize()
}

async function loadImages() {
  try {
    const res = await datasetsApi.fetchImages(id.value, { split: currentSplit.value, page: imagesPage.value, page_size: imagesPageSize })
    images.value = res.data.images
    imagesTotal.value = res.data.total
    imagesTotalPages.value = res.data.total_pages
  } catch (e: any) {
    images.value = []
    imagesTotal.value = 0
    imagesTotalPages.value = 1
  }
}

function switchSplit(s: 'train' | 'val' | 'test') {
  if (currentSplit.value === s) return
  currentSplit.value = s
  imagesPage.value = 1
  loadImages()
}
function changePage(p: number) {
  if (p < 1 || p > imagesTotalPages.value) return
  imagesPage.value = p
  loadImages()
}
function openPreview(img: DatasetImage) {
  viewerImage.value = img.preview_url
  viewerAlt.value = img.filename
  viewerVisible.value = true
}

// 删除
const deleting = ref(false)
const deleteFiles = ref(false)
async function doDelete() {
  if (!confirm(deleteFiles.value ? '将物理删除数据集目录文件，不可恢复，确认删除？' : '将仅删除注册记录（保留原始文件），确认删除？')) return
  deleting.value = true
  errorMsg.value = ''
  try {
    await datasetsApi.delete(id.value, deleteFiles.value)
    router.push('/dataset/datasets')
  } catch (e: any) {
    errorMsg.value = e.response?.data?.message || e.message || '删除失败'
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadDataset()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  classChart?.dispose()
  areaChart?.dispose()
  sizeChart?.dispose()
  classChart = null
  areaChart = null
  sizeChart = null
})
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/dataset/datasets" class="hover:text-brand-700">数据集</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">{{ dataset?.name || id }}</span>
    </div>

    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <i class="fa-solid fa-circle-notch fa-spin text-2xl"></i>
      <div class="mt-3 text-sm">加载中…</div>
    </div>

    <div v-else-if="errorMsg && !dataset" class="py-24 text-center">
      <div class="text-red-600 mb-3"><i class="fa-solid fa-circle-exclamation mr-1.5"></i>{{ errorMsg }}</div>
      <button @click="loadDataset" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
      <router-link to="/dataset/datasets" class="ml-2 text-brand-700 hover:underline text-sm">返回列表</router-link>
    </div>

    <template v-else-if="dataset">
      <!-- 头部 -->
      <div class="flex items-end justify-between mb-6">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-semibold text-ink-primary">{{ dataset.name }}</h1>
            <span class="badge" :class="statusBadge(dataset.status).cls">{{ statusBadge(dataset.status).label }}</span>
            <span class="tag tag-green">目标检测</span>
            <span :class="formatTagStyle(dataset.format).cls" :style="formatTagStyle(dataset.format).style">{{ formatLabel(dataset.format) }}</span>
            <span class="tag" :class="dataset.source === 'built' ? 'tag-blue' : ''">{{ sourceLabel(dataset.source) }}</span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">{{ formatLabel(dataset.format) }} 单一格式 · {{ dataset.image_size || '—' }} · 创建于 {{ dataset.created_at }}</p>
        </div>
        <div class="flex items-center gap-2">
          <button disabled title="格式转换导出将在第二阶段实现"
            class="px-3 py-2 bg-white border border-surface-border rounded-btn text-sm text-ink-tertiary inline-flex items-center gap-2 cursor-not-allowed opacity-60">
            <i class="fa-solid fa-file-arrow-down text-xs"></i> 导出报告
          </button>
          <button disabled title="数据集导出将在第二阶段实现"
            class="px-4 py-2 bg-brand-700 rounded-btn text-sm font-medium text-white inline-flex items-center gap-2 cursor-not-allowed opacity-60">
            <i class="fa-solid fa-download text-xs"></i> 导出数据集
          </button>
          <div class="w-px h-8 bg-surface-border mx-1"></div>
          <label class="flex items-center gap-1.5 text-xs text-ink-secondary cursor-pointer" title="勾选后删除将同时物理删除数据集目录文件">
            <input type="checkbox" v-model="deleteFiles" class="accent-red-600" />
            <span>删除文件</span>
          </label>
          <button @click="doDelete" :disabled="deleting"
            :class="deleteFiles ? 'bg-red-600 hover:bg-red-700' : 'bg-white border border-red-300 text-red-600 hover:bg-red-50'"
            class="px-3 py-2 rounded-btn text-sm font-medium inline-flex items-center gap-1.5 disabled:opacity-50">
            <i class="fa-solid fa-trash text-xs"></i>{{ deleting ? '删除中…' : '删除' }}
          </button>
        </div>
      </div>

      <div v-if="errorMsg" class="mb-4 bg-red-50 border border-red-200 rounded-card p-3 text-xs text-red-600 flex items-center gap-2">
        <i class="fa-solid fa-circle-exclamation"></i>{{ errorMsg }}
      </div>

      <!-- 统计卡片 5 列 -->
      <div class="grid grid-cols-5 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">样本总数</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.sample_count.toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">训练集</div><div class="text-2xl font-semibold text-brand-700 mt-1">{{ dataset.train_count.toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">验证集</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.val_count.toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">测试集</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ (dataset.test_count || 0).toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">标注框数</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.object_count.toLocaleString() }}</div></div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <!-- 数据集结构 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-ink-primary">数据集结构</h3>
              <span class="text-xs text-ink-tertiary font-mono">{{ dataset.path || dataset.name }}</span>
            </div>
            <div class="font-mono text-xs space-y-1 text-ink-primary">
              <div
                v-for="(node, i) in tree"
                :key="i"
                class="flex items-center gap-1.5 py-1"
                :style="{ marginLeft: node.depth * 20 + 'px' }"
              >
                <i class="fa-solid text-xs" :class="[node.icon, node.iconColor]"></i>
                <span :class="node.depth === 0 ? 'font-semibold' : ''">{{ node.name }}</span>
                <span v-if="node.note" class="text-ink-tertiary ml-2">{{ node.note }}</span>
              </div>
            </div>
            <div class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5">
              <i class="fa-solid fa-circle-info text-brand-700"></i>
              本数据集仅管理 {{ formatLabel(dataset.format) }} 格式。其他格式请查看对应独立数据集。
            </div>
          </div>

          <!-- 数据划分 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">数据划分</h3>
            <div class="grid grid-cols-3 gap-4 mb-4">
              <div v-for="row in summaryRows" :key="row.set" class="border border-surface-border rounded-card p-3">
                <div class="flex items-center gap-2 mb-2"><span class="w-2 h-2 rounded-full" :class="row.color" :style="row.set === 'test' ? 'background:#C8E6C9' : ''"></span><span class="text-xs text-ink-secondary">{{ row.set === 'train' ? '训练集' : row.set === 'val' ? '验证集' : '测试集' }}</span></div>
                <div class="text-2xl font-semibold text-ink-primary">{{ Number(row.images).toLocaleString() }}</div>
                <div class="text-xs text-ink-tertiary mt-1">{{ row.pct }}%</div>
              </div>
            </div>
            <div class="split-bar">
              <div class="seg-train" :style="{ flex: dataset.train_count }"></div>
              <div class="seg-val" :style="{ flex: dataset.val_count }"></div>
              <div v-if="dataset.test_count" class="seg-test" :style="{ flex: dataset.test_count }"></div>
            </div>
            <div class="text-xs text-ink-tertiary mt-3">
              <i class="fa-solid fa-circle-check text-brand-700 mr-1"></i>
              已确保同源原图的所有切片都在同一集合内，无数据泄漏 · 划分比例 {{ splitRatioLabel }}
            </div>
          </div>

          <!-- 统计分析报告 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-5">
              <div>
                <h3 class="text-sm font-semibold text-ink-primary">统计分析报告</h3>
                <p class="text-xs text-ink-tertiary mt-0.5">
                  多维度数据质量分析 ·
                  <template v-if="report">
                    {{ report.cached ? '命中缓存' : '已重新生成' }} · {{ report.generated_at }}
                  </template>
                  <template v-else>{{ reportError || '未生成' }}</template>
                </p>
              </div>
              <button @click="loadReport(true)" :disabled="reportLoading"
                class="px-3 py-1.5 bg-brand-50 border border-brand-100 hover:bg-brand-100 text-brand-700 rounded-btn text-xs inline-flex items-center gap-1.5 disabled:opacity-50">
                <i class="fa-solid fa-rotate" :class="reportLoading ? 'fa-spin' : ''"></i>{{ reportLoading ? '生成中…' : '重新生成' }}
              </button>
            </div>

            <div v-if="reportLoading && !report" class="py-12 text-center text-ink-tertiary">
              <i class="fa-solid fa-circle-notch fa-spin text-xl"></i>
              <div class="mt-2 text-xs">正在生成统计报告…</div>
            </div>

            <div v-else-if="report">
              <!-- 1. 数据规模统计 -->
              <div class="mb-6">
                <div class="flex items-center gap-2 mb-3">
                  <span class="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">1</span>
                  <h4 class="text-sm font-medium text-ink-primary">数据规模统计</h4>
                  <span class="text-xs text-ink-tertiary">· 共 {{ report.summary.total_images }} 图 / {{ report.summary.total_objects }} 框 / 原图 {{ report.summary.origin_image_count }} 张 / 非空图 {{ report.summary.non_empty_images }} 张</span>
                </div>
                <div class="overflow-hidden border border-surface-border rounded-btn mb-3">
                  <table class="w-full text-sm">
                    <thead class="bg-surface-bg text-xs text-ink-secondary">
                      <tr>
                        <th class="text-left py-2 px-3 font-medium">集合</th>
                        <th class="text-right py-2 px-3 font-medium">图片数</th>
                        <th class="text-right py-2 px-3 font-medium">占比</th>
                      </tr>
                    </thead>
                    <tbody class="row-hover">
                      <tr v-for="row in summaryRows" :key="row.set" class="border-t border-surface-border">
                        <td class="py-2 px-3"><span class="dot mr-1.5" :class="row.color" :style="row.set === 'test' ? 'background:#C8E6C9' : ''"></span>{{ row.set }}</td>
                        <td class="text-right py-2 px-3 text-ink-primary">{{ Number(row.images).toLocaleString() }}</td>
                        <td class="text-right py-2 px-3 text-ink-secondary">{{ row.pct }}%</td>
                      </tr>
                      <tr class="border-t-2 border-surface-border bg-surface-bg/50 font-medium">
                        <td class="py-2 px-3 text-ink-primary">合计</td>
                        <td class="text-right py-2 px-3 text-ink-primary">{{ dataset.sample_count.toLocaleString() }}</td>
                        <td class="text-right py-2 px-3 text-ink-secondary">100%</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div class="divider mb-6"></div>

              <!-- 2. 类别分布柱状图 -->
              <div class="mb-6">
                <div class="flex items-center gap-2 mb-3">
                  <span class="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">2</span>
                  <h4 class="text-sm font-medium text-ink-primary">类别分布</h4>
                  <span class="text-xs text-ink-tertiary">· {{ report.class_dist.length }} 个类别</span>
                </div>
                <div ref="classChartRef" class="w-full h-64"></div>
              </div>

              <div class="divider mb-6"></div>

              <!-- 3. bbox 面积分布直方图 -->
              <div class="mb-6">
                <div class="flex items-center gap-2 mb-3">
                  <span class="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">3</span>
                  <h4 class="text-sm font-medium text-ink-primary">标注框面积分布</h4>
                  <span class="text-xs text-ink-tertiary">· 平均尺寸 {{ report.bbox_stats.avg_width }} × {{ report.bbox_stats.avg_height }} px</span>
                </div>
                <div ref="areaChartRef" class="w-full h-64"></div>
              </div>

              <div class="divider mb-6"></div>

              <!-- 4. 目标尺度分布（COCO small/medium/large） -->
              <div class="mb-3">
                <div class="flex items-center gap-2 mb-3">
                  <span class="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">4</span>
                  <h4 class="text-sm font-medium text-ink-primary">目标尺度分布</h4>
                  <span class="text-xs text-ink-tertiary">· COCO 标准（small &lt; 32²、medium 32²~96²、large &gt; 96²）</span>
                </div>
                <div ref="sizeChartRef" class="w-full h-48"></div>
              </div>

              <!-- 失衡告警 -->
              <div v-if="report.warnings && report.warnings.length" class="mt-4 bg-amber-50 border border-amber-200 rounded-btn p-3 text-xs text-amber-700">
                <div class="flex items-start gap-1.5">
                  <i class="fa-solid fa-triangle-exclamation mt-0.5"></i>
                  <div>
                    <div class="font-medium mb-0.5">数据质量告警</div>
                    <div v-for="(w, i) in report.warnings" :key="i">{{ w }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="py-8 text-center">
              <div class="text-xs text-ink-tertiary mb-3"><i class="fa-solid fa-circle-info mr-1"></i>{{ reportError || '报告未生成' }}</div>
              <button @click="loadReport(true)" :disabled="reportLoading"
                class="px-4 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm">
                {{ reportLoading ? '生成中…' : '生成报告' }}
              </button>
            </div>
          </div>

          <!-- 样本浏览 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-semibold text-ink-primary">样本浏览</h3>
              <div class="flex gap-2">
                <button v-for="s in (['train','val','test'] as const)" :key="s" @click="switchSplit(s)"
                  class="px-3 py-1 text-xs rounded-btn"
                  :class="currentSplit === s ? 'bg-brand-700 text-white' : 'bg-white border border-surface-border text-ink-secondary hover:bg-surface-hover'">{{ s }}</button>
              </div>
            </div>
            <div v-if="images.length === 0" class="py-12 text-center text-xs text-ink-tertiary">
              <i class="fa-solid fa-images text-2xl mb-2 block"></i>该集合暂无样本图片
            </div>
            <div v-else class="grid grid-cols-6 gap-3">
              <div v-for="img in images" :key="img.filename"
                class="border border-surface-border rounded-btn overflow-hidden cursor-pointer hover:border-brand-300 hover:shadow-sm transition"
                @click="openPreview(img)">
                <div class="aspect-square bg-surface-bg overflow-hidden">
                  <img :src="img.thumbnail_url" :alt="img.filename" class="w-full h-full object-cover" loading="lazy" />
                </div>
                <div class="text-[10px] text-ink-tertiary px-1.5 py-1 truncate font-mono" :title="img.filename">{{ img.filename }}</div>
              </div>
            </div>
            <div v-if="images.length > 0" class="mt-4 flex items-center justify-between text-xs text-ink-tertiary">
              <span>共 {{ imagesTotal }} 张 · 第 {{ imagesPage }}/{{ imagesTotalPages }} 页</span>
              <div class="flex gap-2">
                <button @click="changePage(imagesPage - 1)" :disabled="imagesPage <= 1"
                  class="px-2.5 py-1 border border-surface-border rounded-btn hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed">上一页</button>
                <button @click="changePage(imagesPage + 1)" :disabled="imagesPage >= imagesTotalPages"
                  class="px-2.5 py-1 border border-surface-border rounded-btn hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed">下一页</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 基本信息 -->
        <div class="space-y-5">
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">基本信息</h3>
            <div class="space-y-2.5 text-xs">
              <div class="flex justify-between"><span class="text-ink-tertiary">数据集 ID</span><span class="font-mono text-ink-primary">{{ dataset.id }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">版本</span><span class="text-ink-primary font-medium">{{ dataset.version || '—' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">任务类型</span><span class="text-ink-primary">目标检测</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">标注格式</span><span class="text-ink-primary">{{ formatLabel(dataset.format) }}（单一）</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">来源</span><span class="text-ink-primary">{{ sourceLabel(dataset.source) }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">类别数</span><span class="text-ink-primary">{{ (dataset.classes || []).length }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">原图数</span><span class="text-ink-primary">{{ dataset.origin_image_count || 0 }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">分辨率</span><span class="text-ink-primary">{{ dataset.image_size || '—' }}</span></div>
              <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">存储路径</span><span class="font-mono text-ink-primary text-[11px] text-right break-all">{{ dataset.path }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">创建时间</span><span class="text-ink-primary">{{ dataset.created_at }}</span></div>
              <div v-if="dataset.description" class="flex justify-between gap-2 pt-2 border-t border-surface-border"><span class="text-ink-tertiary flex-shrink-0">描述</span><span class="text-ink-primary text-right">{{ dataset.description }}</span></div>
            </div>
          </div>

          <!-- 类别列表 -->
          <div v-if="dataset.classes && dataset.classes.length" class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">类别列表</h3>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="(c, i) in dataset.classes" :key="i" class="tag tag-green text-xs">
                <span class="font-mono text-[10px] text-ink-tertiary mr-1">{{ i }}</span>{{ c }}
              </span>
            </div>
          </div>

          <!-- 危险操作区 -->
          <div class="bg-white border border-red-200 rounded-card p-5">
            <h3 class="text-sm font-semibold text-red-600 mb-2">删除数据集</h3>
            <p class="text-xs text-ink-tertiary mb-3">从注册中心移除此数据集。默认仅删除注册记录，原始文件保留；勾选「删除文件」将同时物理删除数据集目录。</p>
            <label class="flex items-center gap-2 text-xs text-ink-secondary mb-3 cursor-pointer">
              <input type="checkbox" v-model="deleteFiles" class="accent-red-600" />
              <span>同时删除数据集目录文件（不可恢复）</span>
            </label>
            <button @click="doDelete" :disabled="deleting"
              :class="deleteFiles ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-white border border-red-300 text-red-600 hover:bg-red-50'"
              class="w-full px-3 py-2 rounded-btn text-sm font-medium inline-flex items-center justify-center gap-1.5 disabled:opacity-50">
              <i class="fa-solid fa-trash text-xs"></i>{{ deleting ? '删除中…' : (deleteFiles ? '确认物理删除' : '删除注册记录') }}
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 大图预览 -->
    <ImageViewer :visible="viewerVisible" @update:visible="viewerVisible = $event" :src="viewerImage" :alt="viewerAlt" />
  </AppLayout>
</template>
