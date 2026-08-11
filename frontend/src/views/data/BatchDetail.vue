<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import Icon from '@/components/common/Icon.vue'
import { batchesApi, type Batch, type BatchImage } from '@/api/batches'
import { useRoute, useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const batch = ref<Batch | null>(null)
const images = ref<BatchImage[]>([])
const imageTotal = ref(0)
const imagePage = ref(1)
const imagePageSize = 36
const totalPages = ref(1)
const loadingImages = ref(false)
const loading = ref(true)
const errorMsg = ref('')
const editing = ref(false)
const editForm = ref<Partial<Batch>>({})

// Lightbox
const lightboxIdx = ref(-1)
const lightboxOpen = computed(() => lightboxIdx.value >= 0)

const totalSizeGb = computed(() =>
  ((batch.value?.total_size_bytes || 0) / (1024 ** 3)).toFixed(2),
)
const hasMore = computed(() => imagePage.value < totalPages.value)
const imageFormats = computed(() => batch.value?.image_formats?.join(', ') || '-')

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('process')) return { cls: 'badge-running', label: '进行中' }
  if (s.includes('fail')) return { cls: 'badge-error', label: '失败' }
  if (s.includes('ready') || s.includes('完成')) return { cls: 'badge-success', label: '已接入' }
  return { cls: 'badge-pending', label: status || '待处理' }
}

function thumbUrl(img: BatchImage): string {
  return batchesApi.imagePreviewUrl(id.value, img.filename, 'thumbnail')
}
function mediumUrl(img: BatchImage): string {
  return batchesApi.imagePreviewUrl(id.value, img.filename, 'medium')
}

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const b = await batchesApi.get(id.value)
    batch.value = b.data
    await loadImages(1, true)
  } catch (e: any) {
    errorMsg.value = e.message || '加载架次详情失败'
  } finally {
    loading.value = false
  }
}

async function loadImages(page: number, reset: boolean = false) {
  if (loadingImages.value) return
  loadingImages.value = true
  try {
    const res = await batchesApi.listImages(id.value, { page, page_size: imagePageSize })
    const data = res.data
    if (reset) {
      images.value = data.images
    } else {
      images.value = [...images.value, ...data.images]
    }
    imageTotal.value = data.total
    totalPages.value = data.total_pages
    imagePage.value = data.page
  } catch (e: any) {
    console.error('加载图片失败:', e)
  } finally {
    loadingImages.value = false
  }
}

function loadMore() {
  if (hasMore.value) {
    loadImages(imagePage.value + 1)
  }
}

function startEdit() {
  if (!batch.value) return
  editForm.value = {
    batch_name: batch.value.batch_name,
    crop_type: batch.value.crop_type,
    flight_date: batch.value.flight_date,
    plot_name: batch.value.plot_name || '',
    drone_model: batch.value.drone_model || '',
    flight_altitude_m: batch.value.flight_altitude_m,
    overlap_front: batch.value.overlap_front,
    overlap_side: batch.value.overlap_side,
    description: batch.value.description || '',
  }
  editing.value = true
}

async function saveEdit() {
  try {
    const updated = await batchesApi.update(id.value, editForm.value)
    batch.value = updated.data
    editing.value = false
  } catch (e: any) {
    alert(e.message || '保存失败')
  }
}

function cancelEdit() {
  editing.value = false
}

async function deleteBatch() {
  if (!batch.value) return
  if (!confirm(`确定要删除架次「${batch.value.batch_name}」吗？\n（原始图片文件不会被删除）`)) return
  try {
    await batchesApi.delete(id.value)
    router.push('/data/batches')
  } catch (e: any) {
    alert(e.message || '删除失败')
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
  if (lightboxIdx.value < images.value.length - 1) {
    lightboxIdx.value++
    if (lightboxIdx.value >= images.value.length - 3 && hasMore.value) {
      loadMore()
    }
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 ** 3) return (bytes / (1024 ** 2)).toFixed(1) + ' MB'
  return (bytes / (1024 ** 3)).toFixed(2) + ' GB'
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/batches" class="hover:text-brand-700">数据管理 / 原始架次</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">{{ batch?.batch_name || id }}</span>
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
            <h1 class="text-2xl font-semibold text-ink-primary">{{ batch.batch_name }}</h1>
            <span class="badge" :class="statusBadge(batch.status).cls">{{ statusBadge(batch.status).label }}</span>
            <span class="tag tag-green">{{ batch.crop_type }}</span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">
            采集于 {{ batch.flight_date }} · 登记于 {{ batch.created_at }}
          </p>
        </div>
        <div class="flex gap-2">
          <button
            type="button"
            @click="startEdit"
            class="px-4 py-2 border border-surface-border hover:bg-surface-hover text-ink-primary rounded-btn text-sm font-medium inline-flex items-center gap-2"
          >
            <i class="fa-solid fa-pen text-xs"></i> 编辑
          </button>
          <button
            type="button"
            @click="deleteBatch"
            class="px-4 py-2 border border-red-300 text-red-600 hover:bg-red-50 rounded-btn text-sm font-medium inline-flex items-center gap-2"
          >
            <i class="fa-solid fa-trash-can text-xs"></i> 删除
          </button>
          <router-link
            to="/process/task-new"
            class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
          >
            <i class="fa-solid fa-wand-magic-sparkles text-xs"></i> 创建处理任务
          </router-link>
        </div>
      </div>

      <!-- 编辑表单 -->
      <div v-if="editing" class="bg-white border border-surface-border rounded-card p-5 mb-5">
        <h3 class="text-sm font-semibold text-ink-primary mb-4">编辑架次信息</h3>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">架次名称</label>
            <input v-model="editForm.batch_name" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">作物类型</label>
            <input v-model="editForm.crop_type" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">采集日期</label>
            <input v-model="editForm.flight_date" type="date" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">地块名称</label>
            <input v-model="editForm.plot_name" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">无人机型号</label>
            <input v-model="editForm.drone_model" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">飞行高度 (m)</label>
            <input v-model.number="editForm.flight_altitude_m" type="number" step="0.1" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">前向重叠 (%)</label>
            <input v-model.number="editForm.overlap_front" type="number" step="1" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div>
            <label class="block text-xs font-medium text-ink-primary mb-1.5">侧向重叠 (%)</label>
            <input v-model.number="editForm.overlap_side" type="number" step="1" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
          </div>
          <div class="col-span-2">
            <label class="block text-xs font-medium text-ink-primary mb-1.5">描述</label>
            <textarea v-model="editForm.description" rows="3" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"></textarea>
          </div>
        </div>
        <div class="flex gap-2 mt-4">
          <button @click="saveEdit" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium">保存</button>
          <button @click="cancelEdit" class="px-4 py-2 border border-surface-border hover:bg-surface-hover text-ink-primary rounded-btn text-sm">取消</button>
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
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ totalSizeGb }} <span class="text-sm text-ink-tertiary">GB</span>
          </div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">图片格式</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ imageFormats }}</div>
          <div class="text-xs text-ink-tertiary mt-1">
            {{ images[0] ? `${images[0].width} × ${images[0].height}` : '-' }}
          </div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">采集高度</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">
            {{ batch.flight_altitude_m ?? '-' }} <span class="text-sm text-ink-tertiary">m</span>
          </div>
        </div>
      </div>

      <!-- 元数据 -->
      <div class="bg-white border border-surface-border rounded-card p-5 mb-5">
        <h3 class="text-sm font-semibold text-ink-primary mb-3">元数据</h3>
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div class="flex justify-between"><span class="text-ink-tertiary">架次 ID</span><span class="font-mono">{{ batch.batch_id }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span>{{ batch.crop_type }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">采集日期</span><span>{{ batch.flight_date }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">地块名称</span><span>{{ batch.plot_name || '-' }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">无人机型号</span><span>{{ batch.drone_model || '-' }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">飞行高度</span><span>{{ batch.flight_altitude_m ?? '-' }} m</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">前向重叠</span><span>{{ batch.overlap_front ?? '-' }}%</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">侧向重叠</span><span>{{ batch.overlap_side ?? '-' }}%</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">图片数量</span><span>{{ batch.image_count }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">图片格式</span><span>{{ imageFormats }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">总大小</span><span>{{ formatBytes(batch.total_size_bytes) }}</span></div>
          <div class="flex justify-between"><span class="text-ink-tertiary">登记时间</span><span>{{ batch.created_at }}</span></div>
          <div class="flex justify-between col-span-2">
            <span class="text-ink-tertiary">图片目录</span>
            <span class="font-mono text-right break-all">{{ batch.image_folder_path }}</span>
          </div>
          <div class="flex justify-between col-span-2">
            <span class="text-ink-tertiary">描述</span>
            <span class="text-ink-primary text-right">{{ batch.description || '—' }}</span>
          </div>
        </div>
      </div>

      <!-- 图片网格 -->
      <div class="bg-white border border-surface-border rounded-card p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-ink-primary">原始图片</h3>
          <span class="text-xs text-ink-tertiary">共 {{ imageTotal }} 张 · 已加载 {{ images.length }} 张</span>
        </div>
        <div v-if="images.length === 0" class="py-10 text-center text-ink-tertiary text-sm">
          <i class="fa-regular fa-image text-2xl mb-2 block"></i>暂无图片
        </div>
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
          <div
            v-for="(img, i) in images"
            :key="img.filename + i"
            class="aspect-square bg-gradient-to-br from-green-50 to-amber-50 rounded-btn flex items-center justify-center thumb-wrap cursor-pointer relative"
            @click="openLightbox(i)"
          >
            <img
              :src="thumbUrl(img)"
              :alt="img.filename"
              loading="lazy"
              class="w-full h-full object-cover"
              @error="onImgError"
            />
            <i class="fa-solid fa-image text-2xl text-ink-tertiary opacity-30 absolute"></i>
            <div class="thumb-overlay">{{ img.filename }}</div>
          </div>
        </div>

        <!-- 加载更多 -->
        <div v-if="images.length > 0" class="mt-4 flex flex-col items-center gap-2">
          <button
            v-if="hasMore"
            type="button"
            :disabled="loadingImages"
            @click="loadMore"
            class="px-5 py-2 border border-surface-border hover:bg-surface-hover text-ink-primary rounded-btn text-sm font-medium disabled:opacity-50"
          >
            <i v-if="loadingImages" class="fa-solid fa-circle-notch fa-spin mr-1"></i>
            {{ loadingImages ? '加载中…' : '加载更多' }}
          </button>
          <span class="text-xs text-ink-tertiary">已加载 {{ images.length }} / {{ imageTotal }} 张</span>
        </div>
      </div>
    </template>

    <!-- 大图预览 Lightbox -->
    <div
      v-if="lightboxOpen && images[lightboxIdx]"
      class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center"
      @click.self="closeLightbox"
    >
      <button class="absolute top-4 right-4 text-white" title="关闭" @click="closeLightbox">
        <Icon name="close" :size="28" color="#fff" />
      </button>
      <button
        v-if="lightboxIdx > 0"
        class="absolute left-4 text-white"
        title="上一张"
        @click="prevImg"
      ><Icon name="chevron-left" :size="32" color="#fff" /></button>
      <div class="max-w-4xl max-h-[80vh] flex flex-col items-center">
        <img
          :src="mediumUrl(images[lightboxIdx])"
          :alt="images[lightboxIdx].filename"
          class="max-w-full max-h-[75vh] object-contain rounded-btn"
          @error="onImgError"
        />
        <div class="mt-3 text-white text-xs font-mono">
          {{ images[lightboxIdx].filename }} · {{ lightboxIdx + 1 }} / {{ images.length }}
        </div>
      </div>
      <button
        v-if="lightboxIdx < images.length - 1"
        class="absolute right-4 text-white"
        title="下一张"
        @click="nextImg"
      ><Icon name="chevron-right" :size="32" color="#fff" /></button>
    </div>
  </AppLayout>
</template>
