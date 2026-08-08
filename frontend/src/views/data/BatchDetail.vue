<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { mockApi, type Batch } from '@/api/mock'
import { useRoute } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

// 1:1 迁移 data/batch-detail.html：架次元数据 + 样例图像缩略图网格 + 大图预览
const route = useRoute()
const id = computed(() => String(route.params.id))

const batch = ref<Batch | null>(null)
const images = ref<any[]>([])
const imageTotal = ref(0)
const loading = ref(true)
const errorMsg = ref('')

// 大图预览（lightbox）
const lightboxIdx = ref(-1)
const lightboxOpen = computed(() => lightboxIdx.value >= 0)

const previewImages = computed(() => images.value.slice(0, 12))
const totalSizeGb = computed(() => (((batch.value?.image_count || 0) * 4.2) / 1024).toFixed(1))

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('process') || s.includes('进行')) return { cls: 'badge-running', label: '进行中' }
  if (s.includes('fail') || s.includes('错误')) return { cls: 'badge-error', label: '失败' }
  if (s.includes('ready') || s.includes('接入') || s.includes('完成')) return { cls: 'badge-success', label: status || '已接入' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [b, imgRes] = await Promise.all([
      mockApi.fetchBatch(id.value),
      mockApi.fetchBatchImages(id.value),
    ])
    batch.value = b.data
    images.value = imgRes.data.images || []
    imageTotal.value = imgRes.data.total || 0
  } catch (e: any) {
    errorMsg.value = e.message || '加载架次详情失败'
  } finally {
    loading.value = false
  }
}

function openLightbox(i: number) {
  lightboxIdx.value = i
}
function closeLightbox() {
  lightboxIdx.value = -1
}
function prevImg() {
  if (lightboxIdx.value > 0) lightboxIdx.value--
}
function nextImg() {
  if (lightboxIdx.value < previewImages.value.length - 1) lightboxIdx.value++
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/batches" class="hover:text-brand-700">数据管理 / 原始架次</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">{{ batch?.name || id }}</span>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <i class="fa-solid fa-circle-notch fa-spin text-2xl"></i>
      <div class="mt-3 text-sm">加载中…</div>
    </div>

    <!-- 错误 -->
    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3"><i class="fa-solid fa-circle-exclamation mr-1.5"></i>{{ errorMsg }}</div>
      <button @click="load" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
      <router-link to="/data/batches" class="ml-2 text-brand-700 hover:underline text-sm">返回列表</router-link>
    </div>

    <template v-else-if="batch">
      <!-- 头部 -->
      <div class="flex items-end justify-between mb-6">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-semibold text-ink-primary">{{ batch.name }}</h1>
            <span class="badge" :class="statusBadge(batch.status).cls">{{ statusBadge(batch.status).label }}</span>
            <span class="tag tag-green">{{ batch.crop_type }}</span>
            <span class="tag">幼苗期</span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">
            采集于 {{ batch.flight_date }} · 登记于 {{ batch.created_at }} · 维护者 李研究员
          </p>
        </div>
        <div class="flex gap-2">
          <router-link
            to="/process/task-new"
            class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
          >
            <i class="fa-solid fa-wand-magic-sparkles text-xs"></i> 创建处理任务
          </router-link>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-4 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">原图数量</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ batch.image_count }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">总大小</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ totalSizeGb }} GB</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">图片格式</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">JPEG</div>
          <div class="text-xs text-ink-tertiary mt-1">{{ batch.resolution || '5472 × 3648' }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">采集高度</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ batch.altitude_m }} <span class="text-sm text-ink-tertiary">m</span>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <!-- 元数据 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">元数据</h3>
            <div class="grid grid-cols-2 gap-3 text-xs">
              <div class="flex justify-between"><span class="text-ink-tertiary">架次 ID</span><span class="font-mono">{{ batch.id }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span>{{ batch.crop_type }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">采集日期</span><span>{{ batch.flight_date }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">地块名称</span><span>{{ batch.plot_id || batch.location || '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">无人机型号</span><span>{{ batch.drone_model }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">飞行高度</span><span>{{ batch.altitude_m }} m</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">传感器</span><span>{{ batch.sensor || '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">图片数量</span><span>{{ batch.image_count }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">分辨率</span><span>{{ batch.resolution || '-' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">登记时间</span><span>{{ batch.created_at }}</span></div>
              <div class="flex justify-between col-span-2">
                <span class="text-ink-tertiary">描述</span>
                <span class="text-ink-primary text-right">{{ batch.description || '—' }}</span>
              </div>
            </div>
          </div>

          <!-- 样例图像 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-ink-primary">样例图像</h3>
              <span class="text-xs text-ink-tertiary">共 {{ imageTotal }} 张 · 显示前 {{ previewImages.length }} 张</span>
            </div>
            <div v-if="previewImages.length === 0" class="py-10 text-center text-ink-tertiary text-sm">
              <i class="fa-regular fa-image text-2xl mb-2 block"></i>暂无样例图像
            </div>
            <div v-else class="grid grid-cols-4 gap-2">
              <div
                v-for="(img, i) in previewImages"
                :key="i"
                class="aspect-square bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center thumb-wrap cursor-pointer"
                @click="openLightbox(i)"
              >
                <img
                  :src="mockApi.batchImagePreviewUrl(id, img.file)"
                  :alt="img.file"
                  class="w-full h-full object-cover"
                  @error="onImgError"
                />
                <i class="fa-solid fa-image text-2xl text-ink-tertiary opacity-30 absolute"></i>
                <div class="thumb-overlay">{{ img.file }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-5">
          <!-- 关联任务 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">关联任务</h3>
            <div class="space-y-2 text-xs">
              <router-link to="/process/tasks" class="block p-2.5 hover:bg-surface-hover rounded-btn">
                <div class="text-ink-primary font-medium">CLAHE 增强 v1</div>
                <div class="text-ink-tertiary mt-0.5">已完成 · {{ batch.image_count }} 输入 / {{ batch.image_count }} 输出</div>
              </router-link>
              <router-link to="/process/tasks" class="block p-2.5 hover:bg-surface-hover rounded-btn">
                <div class="text-ink-primary font-medium">滑窗裁切 640/0.05</div>
                <div class="text-ink-tertiary mt-0.5">已完成 · 1,820 个切片</div>
              </router-link>
            </div>
          </div>
          <!-- 所属数据集 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">所属数据集</h3>
            <router-link to="/dataset/datasets" class="block p-3 border border-surface-border rounded-btn hover:border-brand-300">
              <div class="text-sm font-medium text-ink-primary">甘蔗幼苗 v1.2.0</div>
              <div class="text-xs text-ink-tertiary mt-1">v1.2.0 · 已发布</div>
            </router-link>
          </div>
        </div>
      </div>
    </template>

    <!-- 大图预览 Lightbox -->
    <div
      v-if="lightboxOpen"
      class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center"
      @click.self="closeLightbox"
    >
      <button class="absolute top-4 right-4 text-white text-2xl" @click="closeLightbox">
        <i class="fa-solid fa-xmark"></i>
      </button>
      <button
        v-if="lightboxIdx > 0"
        class="absolute left-4 text-white text-2xl"
        @click="prevImg"
      ><i class="fa-solid fa-chevron-left"></i></button>
      <div class="max-w-4xl max-h-[80vh] flex flex-col items-center">
        <img
          :src="mockApi.batchImagePreviewUrl(id, previewImages[lightboxIdx]?.file)"
          class="max-w-full max-h-[75vh] object-contain rounded-btn"
          @error="onImgError"
        />
        <div class="mt-3 text-white text-xs font-mono">
          {{ previewImages[lightboxIdx]?.file }} · {{ lightboxIdx + 1 }} / {{ previewImages.length }}
        </div>
      </div>
      <button
        v-if="lightboxIdx < previewImages.length - 1"
        class="absolute right-4 text-white text-2xl"
        @click="nextImg"
      ><i class="fa-solid fa-chevron-right"></i></button>
    </div>
  </AppLayout>
</template>
