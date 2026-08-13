<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { datasetsApi, type ScanResult } from '@/api/datasets'

const router = useRouter()
const mode = ref<'import' | 'build'>('import')

// ── 导入模式 ──
const importPath = ref('')
const scanResult = ref<ScanResult | null>(null)
const importName = ref('')
const importDesc = ref('')
const scanning = ref(false)
const importing = ref(false)
const scanError = ref('')
const importError = ref('')

async function pickFolder() {
  try {
    const res = await datasetsApi.pickFolder()
    if (res.data.path) importPath.value = res.data.path
  } catch (e: any) {
    scanError.value = e.message || '选择文件夹失败'
  }
}

async function doScan() {
  scanError.value = ''
  scanResult.value = null
  if (!importPath.value) { scanError.value = '请输入数据集目录路径'; return }
  scanning.value = true
  try {
    const res = await datasetsApi.scan(importPath.value)
    scanResult.value = res.data
    if (!importName.value && res.data.valid) importName.value = ''
  } catch (e: any) {
    scanError.value = e.response?.data?.message || e.message || '扫描失败'
  } finally {
    scanning.value = false
  }
}

async function doImport() {
  importError.value = ''
  if (!scanResult.value?.valid) { importError.value = '请先扫描并确认数据集'; return }
  importing.value = true
  try {
    const res = await datasetsApi.import(importPath.value, importName.value || undefined, importDesc.value || undefined)
    router.push(`/dataset/datasets/${res.data.dataset_id}`)
  } catch (e: any) {
    importError.value = e.response?.data?.message || e.message || '导入失败'
  } finally {
    importing.value = false
  }
}

// 两 tab 共用的格式标签样式
function formatTagStyle(fmt: string) {
  if (fmt === 'YOLO') return { cls: 'tag tag-blue', style: '' }
  if (fmt === 'COCO') return { cls: 'tag', style: 'background:#FEF3C7;color:#B45309;' }
  if (fmt === 'VOC') return { cls: 'tag', style: 'background:#F3E8FF;color:#7E22CE;' }
  return { cls: 'tag', style: '' }
}

// ── 构建模式（4 步向导，保留原逻辑，提交禁用 + 阶段二提示） ──
const steps = [
  { n: 1, label: '基础信息' },
  { n: 2, label: '标注格式' },
  { n: 3, label: '拆分策略' },
  { n: 4, label: '目录结构' },
]
const currentStep = ref(1)

const form = ref({
  name: 'sugarcane_v1.3.0',
  version: 'v1.3.0',
  crop_type: '甘蔗',
  description: '甘蔗幼苗检测数据集，覆盖 5m / 8m / 10m 三高度切片。',
  format: '' as '' | 'YOLO' | 'COCO' | 'VOC',
  train: 70,
  val: 20,
  test: 10,
})

const successMsg = ref('')
const errorMsg = ref('')
const submitting = ref(false)

const formats = [
  { key: 'YOLO' as const, label: 'YOLO', desc: '.txt 标注 · 推荐 YOLO 训练', icon: 'fa-file-code', color: 'text-blue-600' },
  { key: 'COCO' as const, label: 'COCO', desc: '.json 标注 · 含实例分割信息', icon: 'fa-file-code', color: 'text-amber-600' },
  { key: 'VOC' as const, label: 'Pascal VOC', desc: '.xml 标注 · 经典 VOC 结构', icon: 'fa-file-code', color: 'text-purple-600' },
]

function selectFormat(f: 'YOLO' | 'COCO' | 'VOC') {
  form.value.format = f
}

const splitSum = computed(() => form.value.train + form.value.val + form.value.test)
const splitValid = computed(() => splitSum.value === 100)

const tree = computed(() => {
  const f = form.value.format
  const root = `${form.value.name || 'dataset'}/`
  if (!f) return [] as { depth: number; icon: string; iconColor: string; name: string; note?: string }[]
  if (f === 'YOLO') {
    return [
      { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'images/' },
      { depth: 2, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'train/', note: '训练图片' },
      { depth: 2, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'val/', note: '验证图片' },
      { depth: 2, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'test/', note: '测试图片' },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'labels/', note: 'YOLO .txt 标注' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-blue-600', name: 'data.yaml', note: 'YOLO 配置' },
      { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
    ]
  }
  if (f === 'COCO') {
    return [
      { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'images/', note: '图片' },
      { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'annotations/', note: 'COCO .json 标注' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'instances_train.json' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-amber-600', name: 'instances_val.json' },
      { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
      { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
    ]
  }
  return [
    { depth: 0, icon: 'fa-folder', iconColor: 'text-amber-500', name: root },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'images/', note: '图片' },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'Annotations/', note: 'VOC .xml 标注' },
    { depth: 1, icon: 'fa-folder', iconColor: 'text-amber-500', name: 'ImageSets/Main/', note: 'train/val/test.txt 清单' },
    { depth: 1, icon: 'fa-file-lines', iconColor: 'text-green-600', name: 'voc_classes.txt' },
    { depth: 1, icon: 'fa-file-lines', iconColor: 'text-ink-tertiary', name: 'list.csv', note: '拆分清单' },
    { depth: 1, icon: 'fa-file-code', iconColor: 'text-ink-tertiary', name: 'dataset_meta.json' },
  ]
})

function stepState(n: number): 'active' | 'done' | '' {
  if (n === currentStep.value) return 'active'
  if (n < currentStep.value) return 'done'
  return ''
}
function lineDone(n: number) {
  return n < currentStep.value
}

function canNext(): boolean {
  if (currentStep.value === 1) return !!(form.value.name && form.value.version && form.value.crop_type)
  if (currentStep.value === 2) return !!form.value.format
  if (currentStep.value === 3) return splitValid.value
  return true
}
function next() {
  if (!canNext()) return
  if (currentStep.value < 4) currentStep.value++
}
function prev() {
  if (currentStep.value > 1) currentStep.value--
}

async function submit() {
  submitting.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    await new Promise((r) => setTimeout(r, 300))
    successMsg.value = '数据集创建成功（V1 演示模式）· 数据未持久化'
  } catch (e: any) {
    errorMsg.value = e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/dataset/datasets" class="hover:text-brand-700">数据集</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">新建数据集</span>
    </div>
    <h1 class="text-2xl font-semibold text-ink-primary mb-1">新建数据集</h1>
    <p class="text-sm text-ink-secondary mb-6">导入已有数据集或构建标准化训练数据集 · 单个数据集仅管理一种标注格式</p>

    <!-- 模式切换 -->
    <div class="flex gap-2 mb-6 border-b border-surface-border">
      <button @click="mode = 'import'" class="px-4 py-2 text-sm font-medium border-b-2 -mb-px"
        :class="mode === 'import' ? 'border-brand-700 text-brand-700' : 'border-transparent text-ink-tertiary hover:text-ink-secondary'">
        <i class="fa-solid fa-file-import mr-1.5"></i> 导入已有数据集
      </button>
      <button @click="mode = 'build'" class="px-4 py-2 text-sm font-medium border-b-2 -mb-px"
        :class="mode === 'build' ? 'border-brand-700 text-brand-700' : 'border-transparent text-ink-tertiary hover:text-ink-secondary'">
        <i class="fa-solid fa-hammer mr-1.5"></i> 构建新数据集
      </button>
    </div>

    <!-- 导入模式 -->
    <div v-show="mode === 'import'" class="grid grid-cols-3 gap-5">
      <div class="col-span-2 space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-4">■ 数据集路径</h2>
          <div class="flex gap-2 mb-3">
            <input v-model="importPath" type="text" placeholder="如 datasets/SSDC-UAV_COCO 或绝对路径"
              class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
            <button @click="pickFolder" class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-secondary">
              <i class="fa-solid fa-folder-open"></i> 选择
            </button>
            <button @click="doScan" :disabled="scanning"
              class="px-4 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium">
              {{ scanning ? '扫描中…' : '扫描预检' }}
            </button>
          </div>
          <div v-if="scanError" class="mb-3 text-xs text-red-600 flex items-center gap-1.5">
            <i class="fa-solid fa-circle-exclamation"></i>{{ scanError }}
          </div>
          <!-- 预检结果 -->
          <div v-if="scanResult && scanResult.valid" class="bg-brand-50/50 border border-brand-100 rounded-btn p-4">
            <div class="flex items-center gap-2 mb-3">
              <i class="fa-solid fa-circle-check text-brand-700"></i>
              <span class="text-sm font-medium text-ink-primary">{{ scanResult.message }}</span>
              <span :class="formatTagStyle(scanResult.format!).cls" :style="formatTagStyle(scanResult.format!).style">{{ scanResult.format }}</span>
            </div>
            <div class="grid grid-cols-4 gap-3 text-xs">
              <div><div class="text-ink-tertiary">图片数</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.image_count.toLocaleString() }}</div></div>
              <div><div class="text-ink-tertiary">标注框数</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.object_count.toLocaleString() }}</div></div>
              <div><div class="text-ink-tertiary">原图数</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.origin_image_count }}</div></div>
              <div><div class="text-ink-tertiary">分辨率</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.image_size }}</div></div>
            </div>
            <div class="mt-2 text-xs text-ink-tertiary">类别：{{ scanResult.classes.join('、') }}</div>
          </div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-4">■ 导入选项（可选）</h2>
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">数据集名称（留空用推断名）</label>
              <input v-model="importName" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">描述</label>
              <textarea v-model="importDesc" rows="2" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 resize-none"></textarea>
            </div>
          </div>
        </div>
      </div>
      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">导入摘要</h3>
          <div class="space-y-2.5 text-xs">
            <div class="flex justify-between"><span class="text-ink-tertiary">路径</span><span class="font-mono text-[11px] text-right">{{ importPath || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">格式</span><span class="text-ink-primary">{{ scanResult?.format || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">图片数</span><span class="text-ink-primary">{{ scanResult?.image_count || 0 }}</span></div>
          </div>
          <div v-if="importError" class="mt-3 text-xs text-red-600">{{ importError }}</div>
          <button @click="doImport" :disabled="importing || !scanResult?.valid"
            class="mt-4 w-full px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium">
            {{ importing ? '导入中…' : '确认导入' }}
          </button>
          <router-link to="/dataset/datasets" class="mt-2 block text-center text-xs text-ink-tertiary hover:text-brand-700">取消</router-link>
        </div>
      </div>
    </div>

    <!-- 构建模式（4 步向导，提交禁用 + 阶段二提示） -->
    <div v-show="mode === 'build'">
      <div class="mb-4 bg-amber-50 border border-amber-200 rounded-card p-3 text-xs text-amber-700 flex items-center gap-2">
        <i class="fa-solid fa-triangle-exclamation"></i>
        数据集构建功能将在第二阶段实现，当前仅支持导入已有数据集。
      </div>

      <!-- 成功提示 -->
      <div v-if="successMsg" class="mb-5 bg-brand-50 border border-brand-300 rounded-card p-4 flex items-start gap-3">
        <i class="fa-solid fa-circle-check text-brand-700 mt-0.5"></i>
        <div class="flex-1">
          <div class="text-sm text-brand-700 font-medium">{{ successMsg }}</div>
          <router-link to="/dataset/datasets" class="mt-2 text-xs text-brand-700 hover:underline inline-flex items-center gap-1">
            <i class="fa-solid fa-arrow-left text-[10px]"></i> 返回数据集列表
          </router-link>
        </div>
      </div>
      <div v-if="errorMsg" class="mb-5 bg-red-50 border border-red-200 rounded-card p-4 text-sm text-red-600 flex items-start gap-3">
        <i class="fa-solid fa-circle-exclamation mt-0.5"></i>{{ errorMsg }}
      </div>

      <!-- 步骤指示器 -->
      <div class="flex items-center mb-8">
        <template v-for="(s, i) in steps" :key="s.n">
          <div class="flex items-center gap-3">
            <div class="step-dot" :class="stepState(s.n)">{{ s.n }}</div>
            <div class="text-sm font-medium" :class="stepState(s.n) === '' ? 'text-ink-tertiary' : 'text-ink-primary'">{{ s.label }}</div>
          </div>
          <div v-if="i < steps.length - 1" class="step-line mx-4 flex-1" :class="{ done: lineDone(s.n) }"></div>
        </template>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <!-- 步骤 1：基础信息 -->
          <div v-show="currentStep === 1" class="bg-white border border-surface-border rounded-card p-6">
            <div class="flex items-center gap-2.5 mb-1">
              <div class="w-6 h-6 rounded-full bg-brand-700 text-white text-xs font-semibold flex items-center justify-center">1</div>
              <h2 class="text-base font-semibold text-ink-primary">基础信息</h2>
            </div>
            <p class="text-xs text-ink-tertiary mb-5 ml-8">为新数据集命名并定义核心属性</p>
            <div class="space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs font-medium text-ink-primary mb-1.5">数据集名称 <span class="text-red-500">*</span></label>
                  <input v-model="form.name" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
                  <p class="text-xs text-ink-tertiary mt-1.5">建议格式：<code class="px-1 py-0.5 bg-surface-hover rounded">作物_版本</code></p>
                </div>
                <div>
                  <label class="block text-xs font-medium text-ink-primary mb-1.5">版本号 <span class="text-red-500">*</span></label>
                  <input v-model="form.version" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">作物类型 <span class="text-red-500">*</span></label>
                <select v-model="form.crop_type" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300">
                  <option>甘蔗</option><option>玉米</option><option>小麦</option><option>水稻</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">描述</label>
                <textarea v-model="form.description" rows="2" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 resize-none"></textarea>
              </div>
            </div>
          </div>

          <!-- 步骤 2：标注格式（单选） -->
          <div v-show="currentStep === 2" class="bg-white border border-surface-border rounded-card p-6">
            <div class="flex items-center gap-2.5 mb-1">
              <div class="w-6 h-6 rounded-full bg-brand-700 text-white text-xs font-semibold flex items-center justify-center">2</div>
              <h2 class="text-base font-semibold text-ink-primary">标注格式</h2>
            </div>
            <p class="text-xs text-ink-tertiary mb-5 ml-8">该数据集的唯一标注格式（单选）· COCO / YOLO / VOC 目录严格分离</p>
            <div class="grid grid-cols-3 gap-3">
              <div
                v-for="f in formats"
                :key="f.key"
                class="select-card"
                :class="{ selected: form.format === f.key }"
                @click="selectFormat(f.key)"
              >
                <div class="flex items-center gap-2 mb-2">
                  <i class="fa-solid text-lg" :class="[f.icon, f.color]"></i>
                  <div class="text-sm font-medium text-ink-primary">{{ f.label }}</div>
                </div>
                <div class="text-xs text-ink-tertiary leading-relaxed">{{ f.desc }}</div>
              </div>
            </div>
            <div class="mt-4 bg-brand-50/50 border border-brand-100 rounded-btn p-3 text-xs text-ink-secondary flex items-start gap-2">
              <i class="fa-solid fa-circle-info text-brand-700 mt-0.5"></i>
              <span>单个数据集仅管理一种标注格式。若同一份图片需要多种格式，请新建独立的数据集，三格式目录严格分离，不混合管理。</span>
            </div>
          </div>

          <!-- 步骤 3：拆分策略 -->
          <div v-show="currentStep === 3" class="bg-white border border-surface-border rounded-card p-6">
            <div class="flex items-center gap-2.5 mb-1">
              <div class="w-6 h-6 rounded-full bg-brand-700 text-white text-xs font-semibold flex items-center justify-center">3</div>
              <h2 class="text-base font-semibold text-ink-primary">拆分策略</h2>
            </div>
            <p class="text-xs text-ink-tertiary mb-5 ml-8">配置 train / val / test 比例（需合计 100%）</p>
            <div class="grid grid-cols-3 gap-3 mb-3">
              <div>
                <div class="text-xs text-ink-tertiary mb-1">训练集 train</div>
                <div class="flex items-center gap-2">
                  <input v-model.number="form.train" type="number" min="0" max="100" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
                  <span class="text-xs text-ink-tertiary">%</span>
                </div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">验证集 val</div>
                <div class="flex items-center gap-2">
                  <input v-model.number="form.val" type="number" min="0" max="100" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
                  <span class="text-xs text-ink-tertiary">%</span>
                </div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">测试集 test</div>
                <div class="flex items-center gap-2">
                  <input v-model.number="form.test" type="number" min="0" max="100" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
                  <span class="text-xs text-ink-tertiary">%</span>
                </div>
              </div>
            </div>
            <div class="split-bar mb-2">
              <div class="seg-train" :style="{ flex: form.train }"></div>
              <div class="seg-val" :style="{ flex: form.val }"></div>
              <div class="seg-test" :style="{ flex: form.test }"></div>
            </div>
            <div class="flex justify-between text-xs text-ink-tertiary">
              <span><span class="dot text-brand-700 mr-1"></span>train {{ form.train }}%</span>
              <span><span class="dot text-brand-300 mr-1"></span>val {{ form.val }}%</span>
              <span><span class="dot text-brand-100 mr-1"></span>test {{ form.test }}%</span>
              <span :class="splitValid ? 'text-brand-700' : 'text-amber-600'">合计 {{ splitSum }}%</span>
            </div>
            <div v-if="!splitValid" class="mt-2 text-xs text-amber-600 flex items-center gap-1.5">
              <i class="fa-solid fa-triangle-exclamation"></i> train + val + test 需等于 100%
            </div>
          </div>

          <!-- 步骤 4：目录结构预览 -->
          <div v-show="currentStep === 4" class="bg-white border border-surface-border rounded-card p-6">
            <div class="flex items-center gap-2.5 mb-1">
              <div class="w-6 h-6 rounded-full bg-brand-700 text-white text-xs font-semibold flex items-center justify-center">4</div>
              <h2 class="text-base font-semibold text-ink-primary">目录结构预览</h2>
            </div>
            <p class="text-xs text-ink-tertiary mb-5 ml-8">基于所选标注格式（{{ form.format || '—' }}）生成的标准化目录结构</p>
            <div v-if="!form.format" class="text-xs text-ink-tertiary py-3">请先在步骤 2 选择标注格式</div>
            <div v-else class="bg-surface-bg border border-surface-border rounded-btn p-4 font-mono text-xs space-y-1 text-ink-primary">
              <div
                v-for="(node, i) in tree"
                :key="i"
                class="flex items-center gap-1.5 py-0.5"
                :style="{ marginLeft: node.depth * 20 + 'px' }"
              >
                <i class="fa-solid" :class="[node.icon, node.iconColor]"></i>
                <span :class="node.depth === 0 ? 'font-semibold' : ''">{{ node.name }}</span>
                <span v-if="node.note" class="text-ink-tertiary ml-2">{{ node.note }}</span>
              </div>
            </div>
            <div class="mt-3 bg-brand-50/50 border border-brand-100 rounded-btn p-3 text-xs text-ink-secondary flex items-start gap-2">
              <i class="fa-solid fa-circle-info text-brand-700 mt-0.5"></i>
              <span>构建后将生成标准 train/val/test 目录、list.csv 拆分清单与单一格式标注文件。</span>
            </div>
          </div>
        </div>

        <!-- 摘要侧栏 -->
        <div class="space-y-5">
          <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">配置摘要</h3>
            <div class="space-y-2.5 text-xs">
              <div class="flex justify-between"><span class="text-ink-tertiary">数据集名称</span><span class="text-ink-primary font-medium">{{ form.name || '—' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">版本</span><span class="text-ink-primary">{{ form.version || '—' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span class="text-ink-primary">{{ form.crop_type }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">标注格式</span><span class="text-ink-primary">{{ form.format || '—' }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">拆分比例</span><span class="text-ink-primary">{{ form.train }} : {{ form.val }} : {{ form.test }}</span></div>
              <div class="flex justify-between"><span class="text-ink-tertiary">输出目录</span><span class="text-ink-primary font-mono text-[11px]">{{ form.name || 'dataset' }}/</span></div>
            </div>
            <div class="divider my-4"></div>
            <div class="text-xs text-ink-tertiary mb-3">
              <i class="fa-solid fa-lightbulb text-amber-500 mr-1"></i>
              构建后将生成标准 train/val/test 目录、list.csv 拆分清单与单一格式标注文件
            </div>
            <div class="flex gap-2">
              <router-link to="/dataset/datasets" class="flex-1 px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center">取消</router-link>
              <button v-if="currentStep > 1" @click="prev" class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary">上一步</button>
              <button
                v-if="currentStep < 4"
                @click="next"
                :disabled="!canNext()"
                class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-btn text-sm font-medium"
              >下一步</button>
              <button
                v-else
                disabled
                class="flex-1 px-3 py-2 bg-brand-700 opacity-50 cursor-not-allowed text-white rounded-btn text-sm font-medium"
              >第二阶段实现</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
