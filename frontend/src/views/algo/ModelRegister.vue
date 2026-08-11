<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import { useModelStore } from '@/stores/model'
import type { RegisterModelForm } from '@/api/models'
import Icon from '@/components/common/Icon.vue'

const router = useRouter()
const modelStore = useModelStore()

const form = reactive<RegisterModelForm>({
  name: '',
  display_name: '',
  engine: 'ultralytics',
  category: 'sugarcane_seedling',
  classes: 'Sugarcane Seedling',
  imgsz: 640,
  conf: 0.25,
  iou: 0.7,
  max_det: 300,
  device: '',
  weight_file: undefined,
})

const weightFileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function onFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    form.weight_file = file
    if (!form.name) {
      const baseName = file.name.replace(/\.pt$/i, '').replace(/_/g, '-')
      form.name = baseName
    }
    if (!form.display_name && form.name) {
      const match = form.name.match(/(yolo)?v?(\d+)([a-z])?-?(.+)?/i)
      if (match) {
        const ver = match[2]
        const size = (match[3] || '').toUpperCase()
        form.display_name = `YOLOv${ver}${size} 甘蔗幼苗`
      }
    }
  }
  target.value = ''
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) {
    form.weight_file = file
    if (!form.name) {
      const baseName = file.name.replace(/\.pt$/i, '').replace(/_/g, '-')
      form.name = baseName
    }
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}
function onDragLeave() {
  dragOver.value = false
}

function clearWeightFile() {
  form.weight_file = undefined
}

const errors = computed(() => {
  const e: Record<string, string> = {}
  if (!form.name.trim()) e.name = 'name 为必填项'
  else if (!/^[a-zA-Z0-9_-]+$/.test(form.name.trim()))
    e.name = 'name 只能包含字母、数字、下划线和连字符'
  if (!form.weight_file) e.weight_file = '请上传权重文件'
  return e
})

const classesArray = computed(() =>
  form.classes.split(',').map((s) => s.trim()).filter(Boolean),
)

const summary = computed(() => ({
  name: form.name || '—',
  engine: form.engine,
  imgszConf: `${form.imgsz} / ${form.conf}`,
  device: form.device || '自动',
  classCount: classesArray.value.length,
  weightFile: form.weight_file?.name || '—',
}))

async function onSubmit() {
  errorMsg.value = ''
  successMsg.value = ''
  if (Object.keys(errors.value).length > 0) {
    errorMsg.value = '请填写必填字段：' + Object.values(errors.value).join('；')
    return
  }
  submitting.value = true
  try {
    await modelStore.registerModel({
      ...form,
      name: form.name.trim(),
      display_name: form.display_name.trim() || form.name.trim(),
      category: form.category.trim(),
    })
    successMsg.value = `模型「${form.name}」注册成功，配置已写入 models.yaml，即将返回列表…`
    setTimeout(() => router.push('/algo/models'), 1000)
  } catch (e: any) {
    errorMsg.value = e?.message || '注册失败，请检查后端服务'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/algo/models" class="hover:text-brand-700 transition-colors">算法管理</router-link>
      <Icon name="chevron-right" :size="10" />
      <span class="text-ink-primary">注册模型</span>
    </div>
    <h1 class="text-2xl font-bold text-ink-primary tracking-tight mb-1.5">注册新模型</h1>
    <p class="text-sm text-ink-secondary mb-5">
      将已训练好的权重上传注册到系统，模型配置将写入 config/models.yaml，权重文件自动重命名保存到 models 目录，注册后可热切换激活
    </p>

    <SubTabs />

    <div v-if="successMsg" class="mb-5 px-4 py-3 bg-brand-50 border border-brand-200 rounded-card text-sm text-brand-700 flex items-center gap-2.5">
      <Icon name="validate" :size="16" class="flex-shrink-0" />{{ successMsg }}
    </div>
    <div v-if="errorMsg" class="mb-5 px-4 py-3 bg-red-50 border border-red-200 rounded-card text-sm text-red-700 flex items-center gap-2.5">
      <Icon name="warning" :size="16" class="flex-shrink-0" />{{ errorMsg }}
    </div>

    <div class="grid grid-cols-3 gap-5">
      <div class="col-span-2 space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">基础配置</h2>
          <p class="text-xs text-ink-tertiary mb-5">对应 config/models.yaml 中单个模型配置字段</p>
          <div class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">name <span class="text-red-500">*</span></label>
                <input
                  v-model="form.name"
                  type="text"
                  placeholder="yolo12s-sugarcane"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300 transition-colors"
                />
                <p class="text-xs text-ink-tertiary mt-1.5">模型唯一标识，格式：{模型版本}-{类别}，如 yolo12s-sugarcane</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">display_name</label>
                <input
                  v-model="form.display_name"
                  type="text"
                  placeholder="YOLOv12s 甘蔗幼苗"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors"
                />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">engine <span class="text-red-500">*</span></label>
                <select
                  v-model="form.engine"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors"
                >
                  <option value="ultralytics">ultralytics</option>
                  <option value="custom">custom</option>
                </select>
                <p class="text-xs text-ink-tertiary mt-1.5">ultralytics 支持 YOLOv5/v8/v9/v10/v11/v12</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">category</label>
                <input
                  v-model="form.category"
                  type="text"
                  placeholder="sugarcane_seedling"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300 transition-colors"
                />
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">权重文件 <span class="text-red-500">*</span></label>
              <input
                ref="weightFileInput"
                type="file"
                accept=".pt,.pth,.onnx"
                class="hidden"
                @change="onFileSelect"
              />
              <div v-if="form.weight_file" class="border border-brand-300 bg-brand-50/50 rounded-btn p-3 flex items-center gap-3">
                <div class="w-9 h-9 bg-brand-100 rounded-btn flex items-center justify-center flex-shrink-0">
                  <Icon name="file-code" :size="16" class="text-brand-700" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5">
                    <Icon name="validate" :size="14" class="text-brand-700 flex-shrink-0" />
                    <span class="text-sm font-medium text-ink-primary truncate">{{ form.weight_file.name }}</span>
                  </div>
                  <div class="text-xs text-ink-tertiary mt-0.5 font-numeric">
                    {{ formatSize(form.weight_file.size) }} · 上传后自动重命名为：<span class="font-mono">{{ form.name.replace(/-/g, '_') }}.pt</span>
                  </div>
                </div>
                <button
                  class="text-ink-tertiary hover:text-red-500 flex-shrink-0 p-1 rounded hover:bg-red-50 transition-colors"
                  title="移除文件"
                  @click="clearWeightFile"
                >
                  <Icon name="close" :size="16" />
                </button>
              </div>
              <div
                v-else
                class="dropzone !p-6 transition-colors"
                :class="{ '!border-brand-500 !bg-brand-50': dragOver }"
                @click="weightFileInput?.click()"
                @dragover="onDragOver"
                @dragleave="onDragLeave"
                @drop="onDrop"
              >
                <Icon name="upload" :size="36" class="text-brand-300 mb-2" />
                <div class="text-sm text-ink-primary font-medium">点击选择或拖拽权重文件到此处</div>
                <div class="text-xs text-ink-tertiary mt-1">支持 .pt 格式（Ultralytics PyTorch 权重），单文件 ≤500MB</div>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">classes <span class="text-red-500">*</span></label>
              <input
                v-model="form.classes"
                type="text"
                placeholder="Sugarcane Seedling"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300 transition-colors font-numeric"
              />
              <p class="text-xs text-ink-tertiary mt-1.5">类别名称列表，多个用英文逗号分隔</p>
            </div>
          </div>
        </div>

        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">推理参数</h2>
          <p class="text-xs text-ink-tertiary mb-5">模型默认推理配置，运行时可在检测工作台覆盖</p>
          <div class="grid grid-cols-3 gap-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">imgsz</label>
              <input
                v-model.number="form.imgsz"
                type="number"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors font-numeric"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">conf</label>
              <input
                v-model.number="form.conf"
                type="number"
                step="0.05"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors font-numeric"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">iou</label>
              <input
                v-model.number="form.iou"
                type="number"
                step="0.05"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors font-numeric"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">max_det</label>
              <input
                v-model.number="form.max_det"
                type="number"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors font-numeric"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">device</label>
              <select
                v-model="form.device"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 transition-colors"
              >
                <option value="">自动（GPU 优先）</option>
                <option value="cpu">CPU</option>
                <option value="0">GPU（cuda:0）</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-4">注册摘要</h3>
          <div class="space-y-3 text-xs">
            <div class="flex justify-between items-center">
              <span class="text-ink-tertiary">name</span>
              <span class="text-ink-primary font-mono truncate max-w-[160px]">{{ summary.name }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-ink-tertiary">engine</span>
              <span class="text-ink-primary">{{ summary.engine }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-ink-tertiary">权重文件</span>
              <span class="text-ink-primary max-w-[140px] truncate" :title="summary.weightFile">{{ summary.weightFile }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-ink-tertiary">imgsz / conf</span>
              <span class="text-ink-primary font-numeric">{{ summary.imgszConf }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-ink-tertiary">device</span>
              <span class="text-ink-primary">{{ summary.device }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-ink-tertiary">类别数</span>
              <span class="text-ink-primary font-numeric">{{ summary.classCount }}</span>
            </div>
          </div>
          <div class="divider my-4"></div>
          <div class="text-xs text-ink-tertiary mb-4 flex items-start gap-1.5">
            <Icon name="info" :size="13" class="text-brand-500 mt-0.5 flex-shrink-0" />
            <span>注册后模型配置将写入 config/models.yaml，权重文件保存到 models/ 目录并自动按模型名重命名</span>
          </div>
          <div class="flex gap-2">
            <router-link
              to="/algo/models"
              class="flex-1 px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center inline-flex items-center justify-center transition-colors font-medium"
            >取消</router-link>
            <button
              :disabled="submitting || Object.keys(errors).length > 0"
              class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 transition-colors"
              @click="onSubmit"
            >
              <Icon v-if="submitting" name="spinner" :size="14" class="animate-spin-slow" />
              {{ submitting ? '注册中…' : '注册模型' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
