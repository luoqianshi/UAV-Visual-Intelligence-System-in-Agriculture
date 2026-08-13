<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { useDatasetsStore } from '@/stores/datasets'
import { ref, onMounted } from 'vue'
import type { Dataset } from '@/api/datasets'

// 1:1 迁移 dataset/datasets.html：格式分布卡片 + 格式筛选 + 数据集列表表格
const store = useDatasetsStore()
const filterFormat = ref('')
const errorMsg = ref('')

const formats = [
  { key: 'YOLO', label: 'YOLO', color: 'text-blue-600', bg: 'bg-blue-50' },
  { key: 'COCO', label: 'COCO', color: 'text-amber-600', bg: 'bg-amber-50' },
  { key: 'VOC', label: 'Pascal VOC', color: 'text-purple-600', bg: 'bg-purple-50' },
]

function formatTagStyle(fmt: string) {
  if (fmt === 'YOLO') return { cls: 'tag tag-blue', style: '' }
  if (fmt === 'COCO') return { cls: 'tag', style: 'background:#FEF3C7;color:#B45309;' }
  if (fmt === 'VOC') return { cls: 'tag', style: 'background:#F3E8FF;color:#7E22CE;' }
  return { cls: 'tag', style: '' }
}

function formatCount(key: string): number {
  return store.formatDist[key] || 0
}

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('ready')) return { cls: 'badge-success', label: '已就绪' }
  if (s.includes('publish') || s.includes('发布')) return { cls: 'badge-success', label: '已发布' }
  if (s.includes('build') || s.includes('构建') || s.includes('process')) return { cls: 'badge-running', label: '构建中' }
  if (s.includes('fail')) return { cls: 'badge-pending', label: '失败' }
  if (s.includes('draft') || s.includes('草稿')) return { cls: 'badge-pending', label: '草稿' }
  return { cls: 'badge-info', label: status || '—' }
}

function splitRatio(d: Dataset): string {
  const total = d.train_count + d.val_count + (d.test_count || 0)
  if (!total) return '—'
  if (!d.test_count) return `${d.train_count}:${d.val_count}`
  return `${d.train_count}:${d.val_count}:${d.test_count}`
}

function sourceLabel(s: string): string {
  return s === 'built' ? '构建' : '导入'
}

async function applyFilter(fmt?: string) {
  filterFormat.value = fmt || ''
  errorMsg.value = ''
  try {
    await store.fetchDatasets({ format: filterFormat.value || undefined })
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  }
}

onMounted(() => applyFilter())
</script>

<template>
  <AppLayout>
    <!-- 头部 -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">数据集管理</div>
        <h1 class="text-2xl font-semibold text-ink-primary">数据集</h1>
        <p class="text-sm text-ink-secondary mt-1">甘蔗幼苗数据集 · 单个数据集仅管理一种标注格式</p>
      </div>
      <div class="flex gap-2">
        <router-link to="/dataset/dataset-new" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2">
          <i class="fa-solid fa-file-import text-xs"></i> 导入数据集
        </router-link>
        <router-link to="/dataset/dataset-new" class="px-4 py-2 bg-white border border-surface-border hover:bg-surface-hover text-ink-primary rounded-btn text-sm font-medium inline-flex items-center gap-2">
          <i class="fa-solid fa-plus text-xs"></i> 新建数据集
        </router-link>
      </div>
    </div>

    <!-- 格式分布统计 -->
    <div class="grid grid-cols-5 gap-4 mb-6">
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">数据集总数</div>
            <div class="text-2xl font-semibold text-ink-primary mt-1">{{ store.total }}</div>
          </div>
          <div class="w-9 h-9 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700"><i class="fa-solid fa-database text-sm"></i></div>
        </div>
      </div>
      <div v-for="f in formats" :key="f.key" class="bg-white border border-surface-border rounded-card p-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">{{ f.label }} 格式</div>
            <div class="text-2xl font-semibold mt-1" :class="f.color">{{ formatCount(f.key) }}</div>
          </div>
          <div class="w-9 h-9 rounded-btn flex items-center justify-center" :class="[f.bg, f.color]"><i class="fa-solid fa-file-code text-sm"></i></div>
        </div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-ink-tertiary">总标注框数</div>
            <div class="text-2xl font-semibold text-ink-primary mt-1">{{ store.datasets.reduce((s, d) => s + (d.object_count || 0), 0).toLocaleString() }}</div>
          </div>
          <div class="w-9 h-9 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700"><i class="fa-solid fa-vector-square text-sm"></i></div>
        </div>
      </div>
    </div>

    <!-- 格式筛选 -->
    <div class="flex items-center gap-2 mb-4">
      <span class="text-xs text-ink-tertiary">筛选格式：</span>
      <button @click="applyFilter('')" class="px-3 py-1 text-xs rounded-btn font-medium" :class="filterFormat === '' ? 'bg-brand-700 text-white' : 'bg-white border border-surface-border hover:bg-surface-hover text-ink-secondary'">
        全部 ({{ store.total }})
      </button>
      <button v-for="f in formats" :key="f.key" @click="applyFilter(f.key)" class="px-3 py-1 text-xs rounded-btn" :class="filterFormat === f.key ? 'bg-brand-700 text-white font-medium' : 'bg-white border border-surface-border hover:bg-surface-hover text-ink-secondary'">
        {{ f.label }} ({{ formatCount(f.key) }})
      </button>
    </div>

    <!-- 数据集列表表格 -->
    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-2.5 px-5 font-medium">数据集名称</th>
            <th class="text-left py-2.5 px-5 font-medium">版本</th>
            <th class="text-left py-2.5 px-5 font-medium">标注格式</th>
            <th class="text-left py-2.5 px-5 font-medium">来源</th>
            <th class="text-right py-2.5 px-5 font-medium">样本数</th>
            <th class="text-right py-2.5 px-5 font-medium">标注框数</th>
            <th class="text-left py-2.5 px-5 font-medium">数据划分</th>
            <th class="text-left py-2.5 px-5 font-medium">状态</th>
            <th class="text-left py-2.5 px-5 font-medium">创建时间</th>
            <th class="text-right py-2.5 px-5 font-medium w-20">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr v-if="store.loading">
            <td colspan="10" class="py-10 text-center text-ink-tertiary text-sm">
              <i class="fa-solid fa-circle-notch fa-spin mr-2"></i> 加载中…
            </td>
          </tr>
          <tr v-else-if="errorMsg">
            <td colspan="10" class="py-10 text-center text-sm">
              <div class="text-red-600 mb-2"><i class="fa-solid fa-circle-exclamation mr-1.5"></i>{{ errorMsg }}</div>
              <button @click="applyFilter(filterFormat)" class="text-brand-700 hover:underline text-xs">重试</button>
            </td>
          </tr>
          <tr v-else-if="store.datasets.length === 0">
            <td colspan="10" class="py-12 text-center text-ink-tertiary">
              <i class="fa-regular fa-folder-open text-2xl mb-2 block"></i>
              <div class="text-sm">暂无数据集</div>
            </td>
          </tr>
          <tr v-for="d in store.datasets" v-else :key="d.id" class="border-t border-surface-border">
            <td class="py-3 px-5">
              <router-link :to="`/dataset/datasets/${d.id}`" class="font-medium text-ink-primary hover:text-brand-700">{{ d.name }}</router-link>
              <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ d.path || d.id }}</div>
            </td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ d.version }}</td>
            <td class="py-3 px-5"><span :class="formatTagStyle(d.format).cls" :style="formatTagStyle(d.format).style">{{ d.format === 'VOC' ? 'Pascal VOC' : d.format }}</span></td>
            <td class="py-3 px-5"><span class="tag" :class="d.source === 'built' ? 'tag-blue' : ''">{{ sourceLabel(d.source) }}</span></td>
            <td class="text-right py-3 px-5 text-ink-primary">{{ d.sample_count.toLocaleString() }}</td>
            <td class="text-right py-3 px-5 text-ink-secondary">{{ d.object_count.toLocaleString() }}</td>
            <td class="py-3 px-5">
              <div class="flex items-center gap-2">
                <div class="split-bar w-24">
                  <div class="seg-train" :style="{ flex: d.train_count }"></div>
                  <div class="seg-val" :style="{ flex: d.val_count }"></div>
                  <div v-if="d.test_count" class="seg-test" :style="{ flex: d.test_count }"></div>
                </div>
                <span class="text-xs text-ink-tertiary">{{ splitRatio(d) }}</span>
              </div>
            </td>
            <td class="py-3 px-5"><span class="badge" :class="statusBadge(d.status).cls">{{ statusBadge(d.status).label }}</span></td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ d.created_at }}</td>
            <td class="py-3 px-5 text-right">
              <router-link :to="`/dataset/datasets/${d.id}`" class="text-xs text-brand-700 hover:underline">查看</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5">
      <i class="fa-solid fa-circle-info text-brand-700"></i>
      单个数据集仅管理一种标注格式，COCO / YOLO / VOC 三种格式目录严格分离；同一份图片数据如需多种格式，请分别新建独立数据集。
    </div>
  </AppLayout>
</template>
