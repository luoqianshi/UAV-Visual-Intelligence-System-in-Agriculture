<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { mockApi, type Dataset } from '@/api/mock'
import { useRoute } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

// 1:1 迁移 dataset/dataset-detail.html：概览 + 目录树 + 数据划分 + 统计分析报告
const route = useRoute()
const id = computed(() => String(route.params.id))

const dataset = ref<Dataset | null>(null)
const report = ref<any>(null)
const reportError = ref('')
const loading = ref(true)
const errorMsg = ref('')

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('publish') || s.includes('发布') || s.includes('ready')) return { cls: 'badge-success', label: '已发布' }
  if (s.includes('build') || s.includes('构建')) return { cls: 'badge-running', label: '构建中' }
  if (s.includes('draft') || s.includes('草稿')) return { cls: 'badge-pending', label: '草稿' }
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
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'images/', note: `${d.sample_count} 张` },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'annotations/', note: 'COCO .json 标注' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'instances_train.json' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'instances_val.json' },
      { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
    ]
  }
  // VOC
  return [
    { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'images/', note: `${d.sample_count} 张` },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'Annotations/', note: 'VOC .xml 标注' },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'ImageSets/Main/', note: 'train/val/test.txt 清单' },
    { depth: 1, icon: 'fa-file-lines', iconColor: 'text-green-600', name: 'voc_classes.txt' },
    { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
    { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
  ]
})

// 统计报告摘要（优先用 report，回退到 dataset）
const summaryRows = computed(() => {
  const d = dataset.value
  if (!d) return []
  const r = report.value
  const pick = (a: any, b: any) => (a !== undefined && a !== null ? a : b)
  return [
    { set: 'train', color: 'text-brand-700', images: pick(r?.train_count, d.train_count), pct: d.train_count && d.sample_count ? ((d.train_count / d.sample_count) * 100).toFixed(1) : '—' },
    { set: 'val', color: 'text-brand-300', images: pick(r?.val_count, d.val_count), pct: d.val_count && d.sample_count ? ((d.val_count / d.sample_count) * 100).toFixed(1) : '—' },
    { set: 'test', color: 'text-brand-100', images: pick(r?.test_count, d.test_count || 0), pct: d.test_count && d.sample_count ? ((d.test_count / d.sample_count) * 100).toFixed(1) : '—' },
  ]
})
const splitRatioLabel = computed(() => {
  const d = dataset.value
  if (!d) return '—'
  if (!d.test_count) return `${d.train_count} : ${d.val_count}`
  return `${d.train_count} : ${d.val_count} : ${d.test_count}`
})
const classDist = computed<any[]>(() => {
  const r = report.value
  if (r?.class_dist && Array.isArray(r.class_dist)) return r.class_dist
  const d = dataset.value
  if (!d) return []
  return (d.classes || []).map((c, i) => ({ name: c, class_id: i, count: r?.total_objects, pct: 100 }))
})

const sizeGb = computed(() => {
  const d = dataset.value
  if (!d) return '—'
  return (d.size_mb / 1024).toFixed(1)
})

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await mockApi.fetchDataset(id.value)
    dataset.value = res.data
    // 统计报告（容错：失败不阻塞页面）
    try {
      const rep = await mockApi.fetchDatasetReport(id.value)
      report.value = rep.data
    } catch (e: any) {
      reportError.value = e.message || '报告未生成'
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载数据集详情失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
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

    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3"><i class="fa-solid fa-circle-exclamation mr-1.5"></i>{{ errorMsg }}</div>
      <button @click="load" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
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
          </div>
          <p class="text-sm text-ink-secondary mt-1">{{ dataset.crop_type }} 数据集 · {{ formatLabel(dataset.format) }} 单一格式 · 创建于 {{ dataset.created_at }} · 维护者 李研究员</p>
        </div>
        <div class="flex gap-2">
          <button class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary inline-flex items-center gap-2">
            <i class="fa-solid fa-file-arrow-down text-xs"></i> 导出报告
          </button>
          <button class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2">
            <i class="fa-solid fa-download text-xs"></i> 导出数据集
          </button>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-5 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">样本总数</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.sample_count.toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">训练集</div><div class="text-2xl font-semibold text-brand-700 mt-1">{{ dataset.train_count.toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">验证集</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.val_count.toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">测试集</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ (dataset.test_count || 0).toLocaleString() }}</div></div>
        <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">存储占用</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ sizeGb }} <span class="text-sm text-ink-tertiary">GB</span></div><div class="text-xs text-ink-tertiary mt-1">{{ (dataset.size_mb || 0).toLocaleString() }} MB</div></div>
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
                <p class="text-xs text-ink-tertiary mt-0.5">多维度数据质量分析 · {{ report ? '已生成' : reportError || '未生成' }}</p>
              </div>
              <div class="flex gap-2">
                <button class="px-3 py-1.5 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-secondary inline-flex items-center gap-1.5"><i class="fa-solid fa-file-lines"></i> Markdown</button>
                <button class="px-3 py-1.5 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-secondary inline-flex items-center gap-1.5"><i class="fa-solid fa-code"></i> HTML</button>
                <button @click="load" class="px-3 py-1.5 bg-brand-50 border border-brand-100 hover:bg-brand-100 text-brand-700 rounded-btn text-xs inline-flex items-center gap-1.5"><i class="fa-solid fa-rotate"></i> 重新生成</button>
              </div>
            </div>

            <!-- 1. 数据规模统计 -->
            <div class="mb-6">
              <div class="flex items-center gap-2 mb-3">
                <span class="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">1</span>
                <h4 class="text-sm font-medium text-ink-primary">数据规模统计</h4>
                <span class="text-xs text-ink-tertiary">· 按 train/val/test 集合汇总</span>
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
              <div class="flex items-center gap-3">
                <div class="split-bar flex-1">
                  <div class="seg-train" :style="{ flex: dataset.train_count }"></div>
                  <div class="seg-val" :style="{ flex: dataset.val_count }"></div>
                  <div v-if="dataset.test_count" class="seg-test" :style="{ flex: dataset.test_count }"></div>
                </div>
                <div class="flex gap-3 text-xs text-ink-tertiary">
                  <span><span class="dot text-brand-700 mr-1"></span>{{ summaryRows[0]?.pct }}%</span>
                  <span><span class="dot text-brand-300 mr-1"></span>{{ summaryRows[1]?.pct }}%</span>
                  <span><span class="dot text-brand-100 mr-1"></span>{{ summaryRows[2]?.pct }}%</span>
                </div>
              </div>
            </div>

            <div class="divider mb-6"></div>

            <!-- 2. 类别分布 -->
            <div>
              <div class="flex items-center gap-2 mb-3">
                <span class="text-xs font-semibold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">2</span>
                <h4 class="text-sm font-medium text-ink-primary">类别分布分析</h4>
                <span class="text-xs text-ink-tertiary">· split_ratio {{ splitRatioLabel }}</span>
              </div>
              <div v-if="classDist.length === 0" class="text-xs text-ink-tertiary py-3">暂无类别分布数据</div>
              <div v-else class="space-y-3">
                <div v-for="(c, i) in classDist" :key="i">
                  <div class="flex items-center justify-between text-xs mb-1.5">
                    <div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-sm bg-brand-500"></span><span class="text-ink-primary font-medium">{{ c.name }}</span><span class="text-ink-tertiary font-mono">class_id={{ c.class_id ?? i }}</span></div>
                    <div class="text-ink-secondary"><span class="text-ink-primary font-semibold">{{ c.count ?? '—' }}</span> 目标 · {{ c.pct ?? 100 }}%</div>
                  </div>
                  <div class="h-5 bg-surface-hover rounded-btn overflow-hidden"><div class="h-full bg-brand-500 rounded-btn" :style="{ width: (c.pct ?? 100) + '%' }"></div></div>
                </div>
              </div>
              <div v-if="reportError" class="mt-3 text-xs text-ink-tertiary">
                <i class="fa-solid fa-circle-info text-brand-300 mr-1"></i>{{ reportError }} · 以上为基于数据集元数据的回退展示
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
              <div class="flex justify-between"><span class="text-ink-tertiary">版本</span><span class="text-ink-primary font-medium">{{ dataset.version }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">任务类型</span><span class="text-ink-primary">目标检测</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">标注格式</span><span class="text-ink-primary">{{ formatLabel(dataset.format) }}（单一）</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span class="text-ink-primary">{{ dataset.crop_type }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">类别数</span><span class="text-ink-primary">{{ (dataset.classes || []).length }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">存储占用</span><span class="text-ink-primary">{{ sizeGb }} GB</span></div>
              <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">输出目录</span><span class="font-mono text-ink-primary text-[11px] text-right">{{ dataset.path }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">创建时间</span><span class="text-ink-primary">{{ dataset.created_at }}</span></div>
              <div v-if="dataset.description" class="flex justify-between gap-2 pt-2 border-t border-surface-border"><span class="text-ink-tertiary flex-shrink-0">描述</span><span class="text-ink-primary text-right">{{ dataset.description }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AppLayout>
</template>
