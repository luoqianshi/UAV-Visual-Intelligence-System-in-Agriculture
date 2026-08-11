<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import DetectionViewer from '@/components/algo/DetectionViewer.vue'
import { useDetectStore } from '@/stores/detect'
import { useModelStore } from '@/stores/model'
import type { Detection } from '@/api/detect'
import Icon from '@/components/common/Icon.vue'

const detectStore = useDetectStore()
const modelStore = useModelStore()

const selectedFile = ref<File | null>(null)
const previewUrl = ref<string>('')
const fileInput = ref<HTMLInputElement | null>(null)
const imgDimensions = ref<{ w: number; h: number } | null>(null)
const isDragging = ref(false)

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  handleFileSelect(file)
  target.value = ''
}

function handleFileSelect(file: File) {
  revokePreview()
  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
  imgDimensions.value = null
  const img = new Image()
  img.onload = () => {
    imgDimensions.value = { w: img.naturalWidth, h: img.naturalHeight }
  }
  img.src = previewUrl.value
}

function clearFile() {
  revokePreview()
  selectedFile.value = null
  imgDimensions.value = null
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

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

const selectedModel = ref<string>('')

onMounted(async () => {
  try {
    await modelStore.fetchModels()
    if (!selectedModel.value) selectedModel.value = modelStore.currentModel
  } catch {
    // 后端未连接时静默
  }
})

watch(
  () => modelStore.currentModel,
  (v) => {
    if (v && !selectedModel.value) selectedModel.value = v
  },
)

const conf = ref(0.25)
const iou = ref(0.7)
const imgsz = ref(640)
const maxDet = ref(300)
const device = ref<string>('')

const canDetect = computed(
  () => !!selectedFile.value && !detectStore.loading && !!selectedModel.value,
)

const activeModelDisplay = computed(() => {
  const m = modelStore.models.find((m) => m.name === modelStore.currentModel)
  return m?.display_name || modelStore.currentModel || '未激活'
})

async function onDetect() {
  if (!selectedFile.value || !selectedModel.value) return
  await detectStore.detectSingle(selectedFile.value, selectedModel.value, {
    conf: conf.value,
    iou: iou.value,
    imgsz: imgsz.value,
    max_det: maxDet.value,
    device: device.value,
  })
}

const detectionList = computed<Detection[]>(() => {
  const list = detectStore.result?.detection_data
    ? [...detectStore.result.detection_data]
    : []
  return list.sort((a, b) => b.confidence - a.confidence)
})
const detectionCount = computed(() => detectStore.result?.detection_count ?? 0)

function downloadResultImage() {
  if (!detectStore.result?.result_image) return
  const a = document.createElement('a')
  a.href = 'data:image/jpeg;base64,' + detectStore.result.result_image
  a.download = 'detect_result.jpg'
  a.click()
}

function downloadJson() {
  if (!detectStore.result?.detection_data) return
  const blob = new Blob(
    [JSON.stringify(detectStore.result.detection_data, null, 2)],
    { type: 'application/json' },
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'detection_data.json'
  a.click()
  URL.revokeObjectURL(url)
}

onBeforeUnmount(() => {
  revokePreview()
  detectStore.stopPolling()
})
</script>

<template>
  <AppLayout>
    <div class="flex items-end justify-between mb-5">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">算法广场</div>
        <h1 class="text-2xl font-bold text-ink-primary tracking-tight">作物检测</h1>
        <p class="text-sm text-ink-secondary mt-1.5">
          单图检测推理 · 快速目标识别与定位
        </p>
      </div>
      <div class="flex items-center gap-2 text-xs text-ink-tertiary">
        <span>当前激活：</span>
        <span class="text-brand-700 font-semibold">{{ activeModelDisplay }}</span>
        <router-link to="/algo/models" class="text-brand-700 hover:underline">切换</router-link>
      </div>
    </div>

    <SubTabs />

    <div v-if="detectStore.loading || detectStore.error" class="mb-5 space-y-3">
      <div
        v-if="detectStore.loading"
        class="bg-white border border-surface-border rounded-card p-4"
      >
        <div class="flex items-center justify-between text-xs mb-2">
          <span class="text-ink-secondary inline-flex items-center gap-1.5">
            <Icon name="spinner" :size="14" class="text-brand-700 animate-spin-slow" />
            正在执行检测…
          </span>
        </div>
        <div class="progress">
          <div class="progress-bar running" style="width: 60%"></div>
        </div>
      </div>
      <div
        v-if="detectStore.error"
        class="bg-red-50 border border-red-200 rounded-card p-3 flex items-start gap-2.5 text-sm text-red-700"
      >
        <Icon name="warning" :size="16" class="mt-0.5 flex-shrink-0" />
        <div class="flex-1">{{ detectStore.error }}</div>
      </div>
    </div>

    <div class="grid grid-cols-3 gap-5">
      <div class="space-y-5">
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
              拖拽图片到此处，或点击选择
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
          <div v-if="selectedFile" class="mt-3 flex items-center gap-3">
            <img
              v-if="previewUrl"
              :src="previewUrl"
              alt="预览"
              class="w-12 h-12 object-cover rounded-btn border border-surface-border flex-shrink-0"
            />
            <div class="text-xs text-ink-tertiary flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <Icon name="validate" :size="14" class="text-brand-700 flex-shrink-0" />
                <span class="text-ink-primary font-medium truncate">{{ selectedFile.name }}</span>
              </div>
              <div class="mt-0.5 font-numeric">
                {{ formatSize(selectedFile.size) }}<span v-if="imgDimensions">
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
        </div>

        <div class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-4">推理参数</h3>
          <div class="space-y-3.5">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">检测模型</label>
              <select
                v-model="selectedModel"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              >
                <option value="" disabled>请选择模型</option>
                <option v-for="m in modelStore.models" :key="m.name" :value="m.name">
                  {{ m.display_name || m.name }}{{ m.is_active ? '（激活）' : '' }}
                </option>
              </select>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">conf 置信度</label>
                <input
                  type="number"
                  step="0.05"
                  v-model.number="conf"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">iou 阈值</label>
                <input
                  type="number"
                  step="0.05"
                  v-model.number="iou"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                />
              </div>
            </div>

            <div class="pt-3 border-t border-surface-border">
              <div class="text-xs font-medium text-ink-primary mb-2.5 flex items-center gap-1.5">
                <Icon name="chip" :size="14" class="text-ink-tertiary" /> 推理尺寸
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">imgsz</label>
                  <input
                    type="number"
                    v-model.number="imgsz"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">max_det</label>
                  <input
                    type="number"
                    v-model.number="maxDet"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 font-numeric"
                  />
                </div>
              </div>
            </div>

            <div>
              <label class="block text-xs font-medium text-ink-secondary mb-1.5">device</label>
              <select
                v-model="device"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              >
                <option value="">自动（GPU 优先）</option>
                <option value="cpu">CPU</option>
                <option value="0">GPU（cuda:0）</option>
              </select>
            </div>
          </div>

          <button
            :disabled="!canDetect"
            @click="onDetect"
            class="w-full mt-4 px-4 py-2.5 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Icon name="bolt" :size="14" />
            {{ detectStore.loading ? '检测中…' : '执行检测' }}
          </button>
        </div>
      </div>

      <div class="col-span-2 space-y-5">
        <div v-if="detectStore.result" class="grid grid-cols-3 gap-4">
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">检测目标</div>
                <div class="text-2xl font-bold text-brand-700 mt-1 font-numeric">
                  {{ detectionCount ?? '—' }}
                  <span class="text-sm text-ink-tertiary font-normal">个</span>
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700">
                <Icon name="cropdetect" :size="18" />
              </div>
            </div>
          </div>
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">最高置信度</div>
                <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">
                  {{ detectionList[0]?.confidence?.toFixed(2) ?? '—' }}
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-blue-50 flex items-center justify-center text-blue-600">
                <Icon name="target" :size="18" />
              </div>
            </div>
          </div>
          <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs text-ink-tertiary">推理尺寸</div>
                <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">
                  {{ imgsz }}
                  <span class="text-sm text-ink-tertiary font-normal">px</span>
                </div>
              </div>
              <div class="w-9 h-9 rounded-btn bg-amber-50 flex items-center justify-center text-amber-600">
                <Icon name="chip" :size="18" />
              </div>
            </div>
          </div>
        </div>

        <div class="bg-white border border-surface-border rounded-card p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-ink-primary">结果展示</h3>
            <div class="flex items-center gap-4 text-xs">
              <span class="text-ink-tertiary font-numeric">
                检测目标 <span class="text-ink-primary font-semibold">{{ detectionCount }}</span>
              </span>
            </div>
          </div>
          <DetectionViewer
            :original-image="previewUrl"
            :result-image="detectStore.result?.result_image"
            :loading="detectStore.loading"
            result-label="检测结果"
          />
          <div class="mt-4 flex items-center gap-2">
            <button
              @click="downloadResultImage"
              :disabled="!detectStore.result?.result_image"
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Icon name="download" :size="12" /> 下载结果图
            </button>
            <button
              @click="downloadJson"
              :disabled="!detectStore.result?.detection_data"
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Icon name="file-code" :size="12" /> 导出 detection_data.json
            </button>
          </div>
        </div>

        <div class="bg-white border border-surface-border rounded-card overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border flex items-center justify-between">
            <h3 class="text-sm font-semibold text-ink-primary">检测结果列表</h3>
            <span class="text-xs text-ink-tertiary font-numeric">
              共 {{ detectionCount }} 条 · 已按置信度降序
            </span>
          </div>
          <div class="overflow-x-auto max-h-[28rem] overflow-y-auto">
            <table v-if="detectionList.length" class="w-full text-sm">
              <thead class="bg-surface-bg text-xs text-ink-secondary sticky top-0 z-10">
                <tr>
                  <th class="text-left py-2.5 px-5 font-medium w-12">#</th>
                  <th class="text-left py-2.5 px-5 font-medium">x</th>
                  <th class="text-left py-2.5 px-5 font-medium">y</th>
                  <th class="text-left py-2.5 px-5 font-medium">width</th>
                  <th class="text-left py-2.5 px-5 font-medium">height</th>
                  <th class="text-left py-2.5 px-5 font-medium">置信度</th>
                  <th class="text-left py-2.5 px-5 font-medium">类别</th>
                </tr>
              </thead>
              <tbody class="row-hover">
                <tr
                  v-for="(d, i) in detectionList"
                  :key="i"
                  class="border-t border-surface-border"
                >
                  <td class="py-2.5 px-5 text-ink-tertiary font-mono text-xs font-numeric">{{ i + 1 }}</td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary font-numeric">
                    {{ d.x.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary font-numeric">
                    {{ d.y.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary font-numeric">
                    {{ d.width.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary font-numeric">
                    {{ d.height.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5">
                    <div
                      class="font-semibold font-numeric"
                      :class="d.confidence >= 0.85 ? 'text-brand-700' : 'text-ink-primary'"
                    >
                      {{ d.confidence.toFixed(2) }}
                    </div>
                  </td>
                  <td class="py-2.5 px-5">
                    <span class="tag tag-green">{{ d.class_name }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div
              v-else
              class="px-5 py-16 flex flex-col items-center justify-center gap-2 text-ink-tertiary"
            >
              <Icon v-if="detectStore.loading" name="spinner" :size="40" class="text-brand-300 mb-1 animate-spin-slow" />
              <Icon v-else name="list-ul" :size="40" class="opacity-30 mb-1" />
              <div class="text-sm">{{ detectStore.loading ? '正在检测…' : '暂无检测结果' }}</div>
              <div class="text-xs">{{ detectStore.loading ? '请稍候' : '上传图片并执行检测后，结果将显示在此处' }}</div>
            </div>
          </div>
          <div
            v-if="detectionList.length"
            class="px-5 py-2.5 border-t border-surface-border text-xs text-ink-tertiary text-center font-numeric"
          >
            共 {{ detectionCount }} 条检测结果
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
