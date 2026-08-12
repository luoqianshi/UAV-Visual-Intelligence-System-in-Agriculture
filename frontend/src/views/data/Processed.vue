<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
import Icon from '@/components/common/Icon.vue'
import { processingApi, type ProcessedItem } from '@/api/processing'
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const router = useRouter()
const items = ref<ProcessedItem[]>([])
const loading = ref(false)
const errorMsg = ref('')

const stats = computed(() => {
  const claheCount = items.value.filter((i) => i.task_type === 'clahe').length
  const cropCount = items.value.filter((i) => i.task_type === 'crop').length
  const totalImages = items.value.reduce((s, i) => s + (i.image_count || 0), 0)
  return { total: items.value.length, claheCount, cropCount, totalImages }
})

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('completed') || s.includes('完成')) return { cls: 'badge-success', label: '已完成' }
  if (s.includes('fail') || s.includes('错误')) return { cls: 'badge-error', label: '失败' }
  if (s.includes('interrupted')) return { cls: 'badge-pending', label: '中断' }
  if (s.includes('process') || s.includes('进行')) return { cls: 'badge-running', label: '进行中' }
  return { cls: 'badge-pending', label: status || '—' }
}

function itemId(item: ProcessedItem): string {
  return item.output_path.split('/').pop() || item.task_id
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.listProcessed()
    items.value = res.data.items
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goDetail(item: ProcessedItem) {
  router.push(`/data/processed/${itemId(item)}`)
}

async function deleteProcessed(item: ProcessedItem, e: Event) {
  e.stopPropagation()
  if (!confirm(`确定删除加工数据「${item.name}」？\n（output 目录将被一并删除）`)) return
  try {
    await processingApi.deleteProcessed(itemId(item), true)
    await load()
  } catch (err: any) {
    alert(err.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <!-- 头部 -->
    <div class="flex items-end justify-between mb-5">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">数据管理 · 加工产物</div>
        <h1 class="text-2xl font-semibold text-ink-primary">加工数据</h1>
        <p class="text-sm text-ink-secondary mt-1">
          浏览数据处理产出的 CLAHE 增强 / 滑窗裁切结果 · 一一对应处理任务
        </p>
      </div>
      <router-link
        to="/process/task-new"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <Icon name="plus" :size="14" /> 新建处理任务
      </router-link>
    </div>

    <DataSubTabs />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-5">
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">加工产物总数</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">{{ stats.total }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">CLAHE 增强产物</div>
        <div class="text-2xl font-semibold text-brand-700 mt-1">{{ stats.claheCount }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">滑窗裁切产物</div>
        <div class="text-2xl font-semibold text-amber-600 mt-1">{{ stats.cropCount }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">总图片数</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">{{ stats.totalImages }}</div>
      </div>
    </div>

    <!-- 加工数据列表表格 -->
    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-2.5 px-5 font-medium">任务名 / ID</th>
            <th class="text-left py-2.5 px-5 font-medium">类型</th>
            <th class="text-left py-2.5 px-5 font-medium">状态</th>
            <th class="text-left py-2.5 px-5 font-medium">输出路径</th>
            <th class="text-right py-2.5 px-5 font-medium">图片数</th>
            <th class="text-left py-2.5 px-5 font-medium">生成时间</th>
            <th class="text-right py-2.5 px-5 font-medium w-28">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr v-if="loading">
            <td colspan="7" class="py-10 text-center text-ink-tertiary text-sm">
              <Icon name="spinner" :size="16" :spin="true" class="inline mr-2" /> 加载中…
            </td>
          </tr>
          <tr v-else-if="errorMsg">
            <td colspan="7" class="py-10 text-center text-sm">
              <div class="text-red-600 mb-2">{{ errorMsg }}</div>
              <button @click="load" class="text-brand-700 hover:underline text-xs">重试</button>
            </td>
          </tr>
          <tr v-else-if="items.length === 0">
            <td colspan="7" class="py-12 text-center text-ink-tertiary">
              <Icon name="augment" :size="32" class="mx-auto mb-2 opacity-40" />
              <div class="text-sm">暂无加工数据</div>
            </td>
          </tr>
          <tr
            v-for="item in items"
            v-else
            :key="item.task_id"
            class="border-t border-surface-border cursor-pointer"
            @click="goDetail(item)"
          >
            <td class="py-3 px-5">
              <div class="font-medium text-ink-primary hover:text-brand-700">{{ item.name }}</div>
              <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ item.task_id }}</div>
            </td>
            <td class="py-3 px-5">
              <span class="tag" :class="item.task_type === 'clahe' ? 'tag-blue' : 'tag-amber'">
                {{ item.task_type === 'clahe' ? 'CLAHE' : '裁切' }}
              </span>
            </td>
            <td class="py-3 px-5">
              <span class="badge" :class="statusBadge(item.status).cls">{{ statusBadge(item.status).label }}</span>
            </td>
            <td class="py-3 px-5 text-ink-tertiary font-mono text-xs">{{ item.output_path }}</td>
            <td class="text-right py-3 px-5 text-ink-primary">{{ item.image_count }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ item.created_at }}</td>
            <td class="py-3 px-5 text-right" @click.stop>
              <router-link
                :to="`/data/processed/${itemId(item)}`"
                class="text-xs text-brand-700 hover:underline mr-2"
              >查看</router-link>
              <button @click="deleteProcessed(item, $event)" class="text-xs text-red-500 hover:underline">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="mt-3 text-xs text-ink-tertiary flex items-center gap-1.5">
      <Icon name="info" :size="12" class="text-brand-700" />
      共 {{ items.length }} 个加工产物 · 点击行可进入详情查看子目录与图片
    </div>
  </AppLayout>
</template>
