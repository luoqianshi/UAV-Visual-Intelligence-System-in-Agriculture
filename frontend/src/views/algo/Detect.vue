<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import DetectionViewer from '@/components/algo/DetectionViewer.vue'
import { useDetectStore } from '@/stores/detect'
import { useModelStore } from '@/stores/model'
import type { Detection } from '@/api/detect'

// 检测工作台：1:1 迁移 algo/detect.html，接入真实 detectStore / modelStore
const detectStore = useDetectStore()
const modelStore = useModelStore()

/* ---------------- 输入源：文件选择 + 预览 ---------------- */
const selectedFile = ref<File | null>(null)
const previewUrl = ref<string>('')
const fileInput = ref<HTMLInputElement | null>(null)
const imgDimensions = ref<{ w: number; h: number } | null>(null)

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
  revokePreview()
  selectedFile.value = file
  previewUrl.value = URL.createObjectURL(file)
  imgDimensions.value = null
  // 读取图片原始尺寸用于信息展示
  const img = new Image()
  img.onload = () => {
    imgDimensions.value = { w: img.naturalWidth, h: img.naturalHeight }
  }
  img.src = previewUrl.value
  // 重置 input value，允许重复选择同一文件
  target.value = ''
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

/* ---------------- 模型选择 ---------------- */
const selectedModel = ref<string>('')

onMounted(async () => {
  try {
    await modelStore.fetchModels()
    if (!selectedModel.value) selectedModel.value = modelStore.currentModel
  } catch {
    // 后端未连接时静默；UI 以空模型列表呈现
  }
})

// currentModel 异步到位后回填
watch(
  () => modelStore.currentModel,
  (v) => {
    if (v && !selectedModel.value) selectedModel.value = v
  },
)

/* ---------------- 推理参数 ---------------- */
const conf = ref(0.25)
const iou = ref(0.7)
const imgsz = ref(640)
const maxDet = ref(300)
const device = ref<string>('')

const canDetect = computed(
  () => !!selectedFile.value && !detectStore.loading && !!selectedModel.value,
)

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

/* ---------------- 结果派生 ---------------- */
const detectionList = computed<Detection[]>(() => {
  const list = detectStore.result?.detection_data
    ? [...detectStore.result.detection_data]
    : []
  return list.sort((a, b) => b.confidence - a.confidence)
})
const detectionCount = computed(() => detectStore.result?.detection_count ?? 0)

/* ---------------- 下载 ---------------- */
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

/* ---------------- 清理 ---------------- */
onBeforeUnmount(() => {
  revokePreview()
  detectStore.stopPolling()
})
</script>

<template>
  <AppLayout>
    <!-- 页头 -->
    <div class="flex items-end justify-between mb-4">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">算法广场</div>
        <h1 class="text-2xl font-semibold text-ink-primary">作物检测</h1>
        <p class="text-sm text-ink-secondary mt-1">
          单图 / 批量检测推理
        </p>
      </div>
      <div class="flex items-center gap-2 text-xs text-ink-tertiary">
        <span>当前激活：</span>
        <span class="text-brand-700 font-medium">{{ modelStore.currentModel || '—' }}</span>
        <router-link to="/algo/models" class="text-brand-700 hover:underline">切换</router-link>
      </div>
    </div>

    <SubTabs />

    <div class="grid grid-cols-3 gap-5">
      <!-- 左：输入与参数 -->
      <div class="space-y-5">
        <!-- 输入源 -->
        <div class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">输入源</h3>
          <div class="flex items-center gap-4 border-b border-surface-border mb-4">
            <div
              class="px-3 py-1.5 text-xs text-brand-700 font-medium border-b-2 border-brand-700 cursor-pointer"
            >
              单张图片
            </div>
            <div
              class="px-3 py-1.5 text-xs text-ink-tertiary border-b-2 border-transparent cursor-not-allowed"
            >
              图片目录（批量）
            </div>
          </div>
          <div class="dropzone !p-6" @click="fileInput?.click()">
            <i class="fa-solid fa-cloud-arrow-up text-3xl text-brand-300 mb-2"></i>
            <div class="text-sm text-ink-primary font-medium">拖拽图片到此处，或点击选择</div>
            <div class="text-xs text-ink-tertiary mt-1">支持 JPG / PNG / BMP / TIFF · 单张 ≤50MB</div>
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              class="hidden"
              @change="onFileChange"
            />
          </div>
          <!-- 已选择文件：缩略图 + 文件名 + 大小 -->
          <div v-if="selectedFile" class="mt-3 flex items-center gap-3">
            <img
              v-if="previewUrl"
              :src="previewUrl"
              alt="预览"
              class="w-12 h-12 object-cover rounded-btn border border-surface-border flex-shrink-0"
            />
            <div class="text-xs text-ink-tertiary flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <i class="fa-regular fa-circle-check text-brand-700"></i>
                <span class="text-ink-primary font-medium truncate">{{ selectedFile.name }}</span>
              </div>
              <div class="mt-0.5">
                {{ formatSize(selectedFile.size) }}<span
                  v-if="imgDimensions"
                  > · {{ imgDimensions.w }}×{{ imgDimensions.h }}</span
                >
              </div>
            </div>
            <button
              class="text-ink-tertiary hover:text-ink-primary flex-shrink-0"
              title="移除"
              @click="clearFile"
            >
              <i class="fa-solid fa-xmark"></i>
            </button>
          </div>
        </div>

        <!-- 推理参数 -->
        <div class="bg-white border border-surface-border rounded-card p-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-4">推理参数</h3>
          <div class="space-y-3.5">
            <!-- 检测模型 -->
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">检测模型</label>
              <select
                v-model="selectedModel"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
              >
                <option value="" disabled>请选择模型</option>
                <option v-for="m in modelStore.models" :key="m.name" :value="m.name">
                  {{ m.display_name || m.name }}{{ m.is_active ? '（激活）' : '' }}
                </option>
              </select>
            </div>
            <!-- conf / iou -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5"
                  >conf 置信度</label
                >
                <input
                  type="number"
                  step="0.05"
                  v-model.number="conf"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5"
                  >iou 阈值</label
                >
                <input
                  type="number"
                  step="0.05"
                  v-model.number="iou"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                />
              </div>
            </div>
            <!-- 推理参数 -->
            <div class="pt-3 border-t border-surface-border">
              <div class="text-xs font-medium text-ink-primary mb-2.5 flex items-center gap-1.5">
                <i class="fa-solid fa-table-cells text-ink-tertiary"></i> 推理参数
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5">imgsz</label>
                  <input
                    type="number"
                    v-model.number="imgsz"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-secondary mb-1.5"
                    >max_det</label
                  >
                  <input
                    type="number"
                    v-model.number="maxDet"
                    class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                  />
                </div>
              </div>
            </div>
            <!-- device -->
            <div>
              <label class="block text-xs font-medium text-ink-secondary mb-1.5">device</label>
              <select
                v-model="device"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
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
            class="w-full mt-4 px-4 py-2.5 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <i class="fa-solid fa-bolt text-xs"></i>
            {{ detectStore.loading ? '检测中…' : '执行检测' }}
          </button>
          <!-- 错误信息 -->
          <div
            v-if="detectStore.error"
            class="mt-3 px-3 py-2 bg-red-50 border border-red-200 rounded-btn text-xs text-red-700 flex items-start gap-2"
          >
            <i class="fa-solid fa-circle-exclamation mt-0.5"></i>
            <span>{{ detectStore.error }}</span>
          </div>
        </div>
      </div>

      <!-- 右：结果展示 + 检测列表 -->
      <div class="col-span-2 space-y-5">
        <!-- 结果展示 -->
        <div class="bg-white border border-surface-border rounded-card p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-ink-primary">结果展示</h3>
            <div class="flex items-center gap-4 text-xs">
              <span class="text-ink-tertiary"
                >检测目标 <span class="text-brand-700 font-medium">{{ detectionCount }}</span></span
              >
            </div>
          </div>
          <DetectionViewer
            :original-image="previewUrl"
            :result-image="detectStore.result?.result_image"
            :loading="detectStore.loading"
          />
          <div class="mt-4 flex items-center gap-2">
            <button
              @click="downloadResultImage"
              :disabled="!detectStore.result?.result_image"
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <i class="fa-solid fa-download text-[10px]"></i> 下载结果图
            </button>
            <button
              @click="downloadJson"
              :disabled="!detectStore.result?.detection_data"
              class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-xs text-ink-primary inline-flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <i class="fa-solid fa-file-code text-[10px]"></i> 导出 detection_data.json
            </button>
          </div>
        </div>

        <!-- 检测结果列表 -->
        <div class="bg-white border border-surface-border rounded-card overflow-hidden">
          <div class="px-5 py-3 border-b border-surface-border flex items-center justify-between">
            <h3 class="text-sm font-semibold text-ink-primary">检测结果列表</h3>
            <span class="text-xs text-ink-tertiary"
              >共 {{ detectionCount }} 条 · 已按置信度降序</span
            >
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
                  <td class="py-2.5 px-5 text-ink-tertiary font-mono text-xs">{{ i + 1 }}</td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary">
                    {{ d.x.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary">
                    {{ d.y.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary">
                    {{ d.width.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5 font-mono text-xs text-ink-primary">
                    {{ d.height.toFixed(1) }}
                  </td>
                  <td class="py-2.5 px-5">
                    <div
                      class="font-semibold"
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
            <!-- 空状态 -->
            <div
              v-else
              class="px-5 py-16 flex flex-col items-center justify-center gap-2 text-ink-tertiary"
            >
              <i class="fa-solid fa-list-ul text-3xl opacity-30"></i>
              <div class="text-sm">暂无检测结果</div>
              <div class="text-xs">上传图片并执行检测后，结果将显示在此处</div>
            </div>
          </div>
          <div
            v-if="detectionList.length"
            class="px-5 py-2.5 border-t border-surface-border text-xs text-ink-tertiary text-center"
          >
            共 {{ detectionCount }} 条检测结果
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
