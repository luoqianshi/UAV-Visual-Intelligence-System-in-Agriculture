<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
import Icon from '@/components/common/Icon.vue'
import ImageViewer from '@/components/common/ImageViewer.vue'
import { processingApi, type ProcessedItem, type TaskFile } from '@/api/processing'
import { useRoute, useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const item = ref<ProcessedItem | null>(null)
const loading = ref(true)
const errorMsg = ref('')

// 当前展开的子目录 + 该子目录已加载的图片列表（用于渐进式加载）
const expandedSubDir = ref<string | null>(null)
const subDirFiles = ref<Record<string, { files: TaskFile[]; total: number; page: number; totalPages: number; loading: boolean }>>({})

// 大图查看器
const viewerVisible = ref(false)
const viewerSrc = ref('')
const viewerAlt = ref('')
function openViewer(src: string, alt: string) {
  if (!src) return
  viewerSrc.value = src
  viewerAlt.value = alt
  viewerVisible.value = true
}
function previewUrl(filename: string, subDir: string, size: 'thumbnail' | 'medium' | 'original' = 'medium'): string {
  if (!item.value) return ''
  return processingApi.previewUrl(item.value.task_id, filename, subDir, size)
}

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('completed') || s.includes('完成')) return { cls: 'badge-success', label: '已完成' }
  if (s.includes('fail') || s.includes('错误')) return { cls: 'badge-error', label: '失败' }
  if (s.includes('interrupted')) return { cls: 'badge-pending', label: '中断' }
  return { cls: 'badge-pending', label: status || '—' }
}

const IMAGE_PAGE_SIZE = 36

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.getProcessed(id.value)
    item.value = res.data
    if (item.value.sub_dirs.length > 0) {
      expandedSubDir.value = item.value.sub_dirs[0].sub_dir
      await loadFiles(item.value.sub_dirs[0].sub_dir, 1, true)
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadFiles(subDir: string, page: number, reset: boolean) {
  if (!item.value) return
  const cur = subDirFiles.value[subDir] || { files: [], total: 0, page: 0, totalPages: 1, loading: false }
  if (cur.loading) return
  cur.loading = true
  subDirFiles.value = { ...subDirFiles.value, [subDir]: { ...cur } }
  try {
    const res = await processingApi.listProcessedFiles(item.value.task_id, {
      sub_dir: subDir,
      page,
      page_size: IMAGE_PAGE_SIZE,
    })
    const next = {
      files: reset ? res.data.files : [...(cur.files || []), ...res.data.files],
      total: res.data.total,
      page: res.data.page,
      totalPages: res.data.total_pages,
      loading: false,
    }
    subDirFiles.value = { ...subDirFiles.value, [subDir]: next }
  } catch {
    subDirFiles.value = { ...subDirFiles.value, [subDir]: { ...cur, loading: false } }
  }
}

async function toggleSubDir(subDir: string) {
  if (expandedSubDir.value === subDir) {
    expandedSubDir.value = null
  } else {
    expandedSubDir.value = subDir
    if (!subDirFiles.value[subDir]) {
      await loadFiles(subDir, 1, true)
    }
  }
}

function loadMore(subDir: string) {
  const cur = subDirFiles.value[subDir]
  if (!cur || cur.loading) return
  if (cur.page < cur.totalPages) {
    loadFiles(subDir, cur.page + 1, false)
  }
}

async function deleteItem() {
  if (!item.value) return
  if (!confirm(`确定删除加工数据「${item.value.name}」？\n（output 目录将被一并删除）`)) return
  try {
    await processingApi.deleteProcessed(id.value, true)
    router.push('/data/processed')
  } catch (e: any) {
    alert(e.message || '删除失败')
  }
}

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/processed" class="hover:text-brand-700">加工数据</router-link>
      <Icon name="chevron-right" :size="10" />
      <span class="text-ink-primary">{{ item?.name || id }}</span>
    </div>

    <DataSubTabs />

    <!-- 加载中 -->
    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <Icon name="spinner" :size="24" :spin="true" class="inline mr-2" /> 加载中…
    </div>

    <!-- 错误 -->
    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3">{{ errorMsg }}</div>
      <button @click="load" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
    </div>

    <template v-else-if="item">
      <!-- 头部 -->
      <div class="flex items-end justify-between mb-5">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-semibold text-ink-primary">{{ item.name }}</h1>
            <span class="badge" :class="statusBadge(item.status).cls">{{ statusBadge(item.status).label }}</span>
            <span class="tag" :class="item.task_type === 'clahe' ? 'tag-blue' : 'tag-amber'">
              {{ item.task_type === 'clahe' ? 'CLAHE 增强' : '滑窗裁切' }}
            </span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">
            生成于 {{ item.created_at }} · {{ item.image_count }} 张图片
          </p>
          <!-- 真实输出路径 -->
          <p class="text-xs text-ink-tertiary mt-1.5 flex items-center gap-1.5 font-mono">
            <Icon name="folder-open" :size="12" class="flex-shrink-0" />
            <span>输出路径：</span>
            <span class="text-ink-secondary break-all">{{ item.output_path }}</span>
          </p>
        </div>
        <div class="flex gap-2">
          <router-link
            v-if="item.has_task"
            :to="`/process/tasks/${item.task_id}`"
            class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary inline-flex items-center gap-2"
          >
            <Icon name="augment" :size="14" /> 查看处理任务
          </router-link>
          <button
            @click="deleteItem"
            class="px-3 py-2 bg-white border border-red-200 hover:bg-red-50 text-red-600 rounded-btn text-sm inline-flex items-center gap-2"
          >
            <Icon name="trash" :size="14" /> 删除
          </button>
        </div>
      </div>

      <!-- 参数与统计 -->
      <div class="bg-white border border-surface-border rounded-card p-5 mb-5">
        <div class="grid grid-cols-4 gap-4 text-sm">
          <div v-for="(val, key) in item.params" :key="key">
            <div class="text-xs text-ink-tertiary">{{ key }}</div>
            <div class="text-ink-primary font-medium mt-0.5">{{ val }}</div>
          </div>
          <div>
            <div class="text-xs text-ink-tertiary">子目录数</div>
            <div class="text-ink-primary font-medium mt-0.5">{{ item.sub_dirs.length }}</div>
          </div>
          <div v-if="item.total_tiles">
            <div class="text-xs text-ink-tertiary">总子图数</div>
            <div class="text-ink-primary font-medium mt-0.5">{{ item.total_tiles }}</div>
          </div>
        </div>
      </div>

      <!-- 子目录与图片（渐进式加载） -->
      <div class="space-y-3">
        <div
          v-for="sub in item.sub_dirs"
          :key="sub.sub_dir"
          class="bg-white border border-surface-border rounded-card overflow-hidden"
        >
          <div
            class="px-5 py-3 border-b border-surface-border flex items-center justify-between cursor-pointer hover:bg-surface-hover"
            @click="toggleSubDir(sub.sub_dir)"
          >
            <div class="flex items-center gap-2">
              <Icon name="folder" :size="16" class="text-ink-tertiary" />
              <span class="font-medium text-ink-primary">{{ sub.sub_dir }}</span>
              <span class="text-xs text-ink-tertiary">
                {{ sub.image_count }} 张<span v-if="sub.tiles_count"> · {{ sub.tiles_count }} tiles</span>
              </span>
            </div>
            <Icon
              :name="expandedSubDir === sub.sub_dir ? 'chevron-down' : 'chevron-right'"
              :size="14"
              class="text-ink-tertiary"
            />
          </div>
          <div v-if="expandedSubDir === sub.sub_dir" class="p-5">
            <div
              v-if="!subDirFiles[sub.sub_dir] || (subDirFiles[sub.sub_dir].files.length === 0 && !subDirFiles[sub.sub_dir].loading)"
              class="text-center text-ink-tertiary text-sm py-4"
            >
              暂无图片
            </div>
            <div v-else>
              <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
                <div
                  v-for="f in subDirFiles[sub.sub_dir].files"
                  :key="f.filename"
                  class="text-center cursor-zoom-in group"
                  @click="openViewer(previewUrl(f.filename, sub.sub_dir, 'original'), `${sub.sub_dir} / ${f.filename}`)"
                >
                  <div class="aspect-square bg-gradient-to-br from-green-50 to-amber-50 rounded-btn border border-surface-border overflow-hidden relative">
                    <img
                      :src="f.thumbnail_url"
                      :alt="f.filename"
                      loading="lazy"
                      class="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                      @error="onImgError"
                    />
                  </div>
                  <div class="text-[10px] text-ink-tertiary mt-1 truncate font-mono" :title="f.filename">{{ f.filename }}</div>
                </div>
              </div>

              <!-- 加载更多 -->
              <div class="mt-4 flex flex-col items-center gap-2">
                <template v-if="subDirFiles[sub.sub_dir].page < subDirFiles[sub.sub_dir].totalPages">
                  <button
                    type="button"
                    :disabled="subDirFiles[sub.sub_dir].loading"
                    @click="loadMore(sub.sub_dir)"
                    class="px-5 py-2 border border-surface-border hover:bg-surface-hover text-ink-primary rounded-btn text-sm font-medium disabled:opacity-50 inline-flex items-center gap-1.5"
                  >
                    <Icon v-if="subDirFiles[sub.sub_dir].loading" name="spinner" :size="14" :spin="true" />
                    {{ subDirFiles[sub.sub_dir].loading ? '加载中…' : '加载更多' }}
                  </button>
                </template>
                <span class="text-xs text-ink-tertiary font-numeric">
                  已加载 {{ subDirFiles[sub.sub_dir].files.length }} / {{ subDirFiles[sub.sub_dir].total }} 张
                  <span v-if="subDirFiles[sub.sub_dir].page >= subDirFiles[sub.sub_dir].totalPages">· 已全部加载</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 大图查看器 -->
      <ImageViewer v-model:visible="viewerVisible" :src="viewerSrc" :alt="viewerAlt" />
    </template>
  </AppLayout>
</template>
