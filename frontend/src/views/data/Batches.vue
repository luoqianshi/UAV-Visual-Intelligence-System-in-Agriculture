<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
import Icon from '@/components/common/Icon.vue'
import { batchesApi, type Batch } from '@/api/batches'
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const router = useRouter()

const batches = ref<Batch[]>([])
const summary = ref({
  total_batches: 0,
  total_images: 0,
  total_size_bytes: 0,
  resolutions: [] as string[],
  formats: [] as string[],
})
const loading = ref(false)
const searchName = ref('')
const filterCrop = ref('')
const errorMsg = ref('')

const crops = computed(() => {
  const set = new Set<string>()
  batches.value.forEach((b) => set.add(b.crop_type))
  return Array.from(set)
})

const totalSizeGb = computed(() =>
  (summary.value.total_size_bytes / (1024 ** 3)).toFixed(2),
)
const resolutionLabel = computed(() => summary.value.resolutions[0] || '-')
const formatsLabel = computed(() => summary.value.formats.join('、') || '-')

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('process') || s.includes('进行') || s.includes('run'))
    return { cls: 'badge-running', label: '进行中' }
  if (s.includes('fail') || s.includes('错误') || s.includes('error'))
    return { cls: 'badge-error', label: '失败' }
  if (s.includes('ready') || s.includes('接入') || s.includes('完成') || s.includes('publish'))
    return { cls: 'badge-success', label: '已接入' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

async function applyFilters() {
  errorMsg.value = ''
  loading.value = true
  try {
    const res = await batchesApi.list({
      crop_type: filterCrop.value || undefined,
    })
    let list = res.data.batches
    if (searchName.value) {
      const q = searchName.value.toLowerCase()
      list = list.filter(
        (b) =>
          b.batch_name.toLowerCase().includes(q) ||
          (b.plot_name || '').toLowerCase().includes(q),
      )
    }
    batches.value = list
    summary.value = res.data.summary
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchName.value = ''
  filterCrop.value = ''
  applyFilters()
}

async function deleteBatch(b: Batch) {
  if (!confirm(`确定要删除架次「${b.batch_name}」吗？\n（原始图片文件不会被删除）`)) return
  try {
    await batchesApi.delete(b.batch_id)
    await applyFilters()
  } catch (e: any) {
    alert(e.message || '删除失败')
  }
}

onMounted(applyFilters)

function goDetail(b: Batch) {
  router.push(`/data/batches/${b.batch_id}`)
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
          按架次浏览本机路径下的大田农作物原始图像 · 每个架次文件夹代表一次拍摄
        </p>
      </div>
      <router-link
        to="/data/batch-new"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <Icon name="plus" :size="14" /> 新建架次
      </router-link>
    </div>

    <DataSubTabs />

    <!-- 原始飞行数据总览：4 张独立卡片（与加工数据一致） -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="text-xs text-ink-tertiary">架次数</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1 font-numeric">
          {{ summary.total_batches }} <span class="text-sm text-ink-tertiary font-normal">个</span>
        </div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="text-xs text-ink-tertiary">载入图片总数</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1 font-numeric">
          {{ summary.total_images }} <span class="text-sm text-ink-tertiary font-normal">张</span>
        </div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="text-xs text-ink-tertiary">总大小</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1 font-numeric">
          {{ totalSizeGb }} <span class="text-sm text-ink-tertiary font-normal">GB</span>
        </div>
        <div class="text-xs text-ink-tertiary mt-1">MIPI · {{ formatsLabel }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
        <div class="text-xs text-ink-tertiary">主要分辨率</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1 font-numeric">{{ resolutionLabel }}</div>
        <div class="text-xs text-ink-tertiary mt-1">{{ formatsLabel }}</div>
      </div>
    </div>

    <!-- 检索栏 -->
    <div class="bg-white border border-surface-border rounded-card p-4 mb-4">
      <div class="grid grid-cols-4 gap-3">
        <div class="relative">
          <Icon name="search" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
          <input
            v-model="searchName"
            type="text"
            placeholder="架次名称 / 地块"
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
        <div></div>
        <div class="flex gap-2">
          <button
            @click="applyFilters"
            class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center justify-center gap-1.5"
          >
            <Icon name="search" :size="12" /> 搜索
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
            <th class="text-left py-2.5 px-5 font-medium">地块</th>
            <th class="text-left py-2.5 px-5 font-medium">机型</th>
            <th class="text-left py-2.5 px-5 font-medium">高度</th>
            <th class="text-right py-2.5 px-5 font-medium">图片数</th>
            <th class="text-left py-2.5 px-5 font-medium">状态</th>
            <th class="text-right py-2.5 px-5 font-medium w-28">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr v-if="loading">
            <td colspan="9" class="py-10 text-center text-ink-tertiary text-sm">
              <Icon name="spinner" :size="16" :spin="true" class="inline mr-2" /> 加载中…
            </td>
          </tr>
          <tr v-else-if="errorMsg">
            <td colspan="9" class="py-10 text-center text-sm">
              <div class="text-red-600 mb-2">{{ errorMsg }}</div>
              <button @click="applyFilters" class="text-brand-700 hover:underline text-xs">重试</button>
            </td>
          </tr>
          <tr v-else-if="batches.length === 0">
            <td colspan="9" class="py-12 text-center text-ink-tertiary">
              <Icon name="database" :size="32" class="mx-auto mb-2 opacity-40" />
              <div class="text-sm">暂无架次记录</div>
            </td>
          </tr>
          <tr
            v-for="b in batches"
            v-else
            :key="b.batch_id"
            class="border-t border-surface-border cursor-pointer"
            @click="goDetail(b)"
          >
            <td class="py-3 px-5">
              <div class="font-medium text-ink-primary hover:text-brand-700">{{ b.batch_name }}</div>
              <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ b.batch_id }}</div>
            </td>
            <td class="py-3 px-5"><span class="tag tag-green">{{ b.crop_type }}</span></td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.flight_date }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.plot_name || '-' }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ b.drone_model || '-' }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">
              {{ b.flight_altitude_m ? b.flight_altitude_m + ' m' : '-' }}
            </td>
            <td class="text-right py-3 px-5 text-ink-primary">{{ b.image_count }}</td>
            <td class="py-3 px-5">
              <span class="badge" :class="statusBadge(b.status).cls">{{ statusBadge(b.status).label }}</span>
            </td>
            <td class="py-3 px-5 text-right" @click.stop>
              <router-link :to="`/data/batches/${b.batch_id}`" class="text-xs text-brand-700 hover:underline mr-2">查看</router-link>
              <button @click="deleteBatch(b)" class="text-xs text-red-500 hover:underline">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5">
      <Icon name="info" :size="12" class="text-brand-700" />
      共 {{ batches.length }} 个架次 · 点击行可进入架次详情查看元数据与图像
    </div>
  </AppLayout>
</template>
