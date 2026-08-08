<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { useMockStore } from '@/stores/mock'
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'
import type { Batch } from '@/api/mock'

// 1:1 迁移 data/batches.html：原始飞行数据总览 + 检索栏 + 架次列表表格
const router = useRouter()
const store = useMockStore()

const searchName = ref('')
const filterCrop = ref('')
const filterStatus = ref('')
const errorMsg = ref('')

const crops = computed(() => {
  const set = new Set<string>()
  store.batches.forEach((b) => set.add(b.crop_type))
  return Array.from(set)
})

const totalImages = computed(() =>
  store.batches.reduce((s, b) => s + (b.image_count || 0), 0),
)
const totalSizeGb = computed(() => ((totalImages.value * 4.2) / 1024).toFixed(1))
const resolutionLabel = computed(() => store.batches[0]?.resolution || '5472 × 3648')

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('process') || s.includes('进行') || s.includes('run'))
    return { cls: 'badge-running', label: '进行中' }
  if (s.includes('fail') || s.includes('错误') || s.includes('error'))
    return { cls: 'badge-error', label: '失败' }
  if (s.includes('ready') || s.includes('接入') || s.includes('完成') || s.includes('publish') || s.includes('发布'))
    return { cls: 'badge-success', label: status || '已接入' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

async function applyFilters() {
  errorMsg.value = ''
  try {
    await store.fetchBatches({
      crop_type: filterCrop.value || undefined,
      status: filterStatus.value || undefined,
    })
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  }
}

function resetFilters() {
  searchName.value = ''
  filterCrop.value = ''
  filterStatus.value = ''
  applyFilters()
}

onMounted(applyFilters)

function goDetail(b: Batch) {
  router.push(`/data/batches/${b.id}`)
}
</script>

<template>
  <AppLayout>
    <!-- 头部 -->
    <div class="flex items-end justify-between mb-6">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">数据管理 · 原始飞行数据</div>
        <h1 class="text-2xl font-semibold text-ink-primary">原始架次</h1>
        <p class="text-sm text-ink-secondary mt-1">
          按架次浏览本机路径下的甘蔗幼苗原始图像 · 每个架次文件夹代表一次拍摄
        </p>
      </div>
      <router-link
        to="/data/batch-new"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <i class="fa-solid fa-plus text-xs"></i> 新建架次
      </router-link>
    </div>

    <!-- 原始飞行数据总览 -->
    <div class="bg-white border border-surface-border rounded-card p-5 mb-6">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
            <i class="fa-solid fa-folder-tree text-sm"></i>
          </div>
          <h2 class="text-sm font-semibold text-ink-primary">原始飞行数据总览</h2>
        </div>
        <span class="text-xs text-ink-tertiary">
          载入路径：<span class="font-mono">/data/raw</span>
        </span>
      </div>
      <div class="grid grid-cols-4 gap-4">
        <div>
          <div class="text-xs text-ink-tertiary">架次数</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ store.batchTotal }} <span class="text-sm text-ink-tertiary font-normal">个</span>
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-tertiary">载入图片总数</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ totalImages }} <span class="text-sm text-ink-tertiary font-normal">张</span>
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-tertiary">作物类型</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">甘蔗</div>
          <div class="text-xs text-ink-tertiary mt-0.5">幼苗期</div>
        </div>
        <div>
          <div class="text-xs text-ink-tertiary">总大小 / 格式</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ totalSizeGb }} <span class="text-sm text-ink-tertiary font-normal">GB</span>
          </div>
          <div class="text-xs text-ink-tertiary mt-0.5">JPEG · {{ resolutionLabel }}</div>
        </div>
      </div>
    </div>

    <!-- 检索栏 -->
    <div class="bg-white border border-surface-border rounded-card p-4 mb-4">
      <div class="grid grid-cols-4 gap-3">
        <div class="relative">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary text-xs"></i>
          <input
            v-model="searchName"
            type="text"
            placeholder="架次名称"
            class="w-full pl-8 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
          />
        </div>
        <select
          v-model="filterCrop"
          @change="applyFilters"
          class="px-3 py-2 bg-white border border-surface-border rounded-btn text-sm text-ink-secondary"
        >
          <option value="">全部作物</option>
          <option v-for="c in crops" :key="c" :value="c">{{ c }}</option>
        </select>
        <select
          v-model="filterStatus"
          @change="applyFilters"
          class="px-3 py-2 bg-white border border-surface-border rounded-btn text-sm text-ink-secondary"
        >
          <option value="">全部状态</option>
          <option value="ready">已接入</option>
          <option value="processing">进行中</option>
          <option value="failed">失败</option>
        </select>
        <div class="flex gap-2">
          <button
            @click="applyFilters"
            class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center justify-center gap-1.5"
          >
            <i class="fa-solid fa-magnifying-glass text-xs"></i> 搜索
          </button>
          <button
            @click="resetFilters"
            class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-secondary"
          >
            重置
          </button>
        </div>
      </div>
    </div>

    <!-- 架次列表表格 -->
    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-2.5 px-5 font-medium">架次名称 / ID</th>
            <th class="text-left py-2.5 px-5 font-medium">作物</th>
            <th class="text-left py-2.5 px-5 font-medium">飞行日期</th>
            <th class="text-left py-2.5 px-5 font-medium">地点</th>
            <th class="text-left py-2.5 px-5 font-medium">机型</th>
            <th class="text-right py-2.5 px-5 font-medium">图片数</th>
            <th class="text-left py-2.5 px-5 font-medium">状态</th>
            <th class="text-right py-2.5 px-5 font-medium w-20">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr v-if="store.loading">
            <td colspan="8" class="py-10 text-center text-ink-tertiary text-sm">
              <i class="fa-solid fa-circle-notch fa-spin mr-2"></i> 加载中…
            </td>
          </tr>
          <tr v-else-if="errorMsg">
            <td colspan="8" class="py-10 text-center text-sm">
              <div class="text-red-600 mb-2"><i class="fa-solid fa-circle-exclamation mr-1.5"></i>{{ errorMsg }}</div>
              <button @click="applyFilters" class="text-brand-700 hover:underline text-xs">重试</button>
            </td>
          </tr>
          <tr v-else-if="store.batches.length === 0">
            <td colspan="8" class="py-12 text-center text-ink-tertiary">
              <i class="fa-regular fa-folder-open text-2xl mb-2 block"></i>
              <div class="text-sm">暂无架次记录</div>
            </td>
          </tr>
          <tr
            v-for="b in store.batches"
            v-else
            :key="b.id"
            class="border-t border-surface-border cursor-pointer"
            @click="goDetail(b)"
          >
            <td class="py-3 px-5">
              <div class="font-medium text-ink-primary hover:text-brand-700">{{ b.name }}</div>
              <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ b.id }}</div>
            </td>
            <td class="py-3 px-5"><span class="tag tag-green">{{ b.crop_type }}</span></td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.flight_date }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.location || b.plot_id || '-' }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.drone_model }}</td>
            <td class="text-right py-3 px-5 text-ink-primary">{{ b.image_count }}</td>
            <td class="py-3 px-5">
              <span class="badge" :class="statusBadge(b.status).cls">{{ statusBadge(b.status).label }}</span>
            </td>
            <td class="py-3 px-5 text-right" @click.stop>
              <router-link :to="`/data/batches/${b.id}`" class="text-xs text-brand-700 hover:underline">查看</router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5">
      <i class="fa-solid fa-circle-info text-brand-700"></i>
      共 {{ store.batchTotal }} 个架次 · 点击行可进入架次详情查看元数据与样例图像
    </div>
  </AppLayout>
</template>
