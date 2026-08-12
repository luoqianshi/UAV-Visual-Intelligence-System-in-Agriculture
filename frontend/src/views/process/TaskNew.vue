<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { batchesApi, type Batch } from '@/api/batches'
import { processingApi, type ProcessedItem } from '@/api/processing'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '@/components/common/Icon.vue'

const router = useRouter()

// 1:1 迁移 process/task-new.html：4 步引导式向导（类型 → 输入源 → 参数 → 确认）
const batches = ref<Batch[]>([])
const processedItems = ref<ProcessedItem[]>([])

const steps = [
  { n: 1, label: '选择类型' },
  { n: 2, label: '选择输入源' },
  { n: 3, label: '配置参数' },
  { n: 4, label: '确认提交' },
]
const currentStep = ref(1)

const selectedType = ref<'clahe' | 'crop' | ''>('clahe')
const selectedBatchIds = ref<string[]>([])
const inputMode = ref<'batch' | 'data' | 'dir'>('batch')
const customDir = ref('')
const selectedProcessedIds = ref<string[]>([])

function generateDefaultName(type: 'clahe' | 'crop'): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  return type === 'clahe' ? `CLAHE增强_${ts}` : `滑窗裁切_${ts}`
}

const form = ref({
  name: generateDefaultName('clahe'),
  clip_limit: 2.0,
  grid: '8 × 8',
  tile_size: 640,
  overlap_ratio: 0.05,
  output_path: 'output/',
})

const successMsg = ref('')
const errorMsg = ref('')
const submitting = ref(false)
const picking = ref(false)

const selectedBatches = computed(() =>
  batches.value.filter((b) => selectedBatchIds.value.includes(b.batch_id)),
)
const selectedImageCount = computed(() =>
  selectedBatches.value.reduce((s, b) => s + (b.image_count || 0), 0),
)
const selectedProcessedItems = computed(() =>
  processedItems.value.filter((p) => selectedProcessedIds.value.includes(p.task_id)),
)
const selectedProcessedImageCount = computed(() =>
  selectedProcessedItems.value.reduce((s, p) => s + (p.image_count || 0), 0),
)

function selectType(t: 'clahe' | 'crop') {
  selectedType.value = t
  form.value.name = generateDefaultName(t)
  form.value.output_path = 'output/'
}

function toggleBatch(bid: string) {
  const i = selectedBatchIds.value.indexOf(bid)
  if (i >= 0) selectedBatchIds.value.splice(i, 1)
  else selectedBatchIds.value.push(bid)
}
function toggleAll() {
  if (selectedBatchIds.value.length === batches.value.length) selectedBatchIds.value = []
  else selectedBatchIds.value = batches.value.map((b) => b.batch_id)
}
function toggleProcessed(pid: string) {
  const i = selectedProcessedIds.value.indexOf(pid)
  if (i >= 0) selectedProcessedIds.value.splice(i, 1)
  else selectedProcessedIds.value.push(pid)
}

function stepState(n: number): 'active' | 'done' | '' {
  if (n === currentStep.value) return 'active'
  if (n < currentStep.value) return 'done'
  return ''
}
function lineDone(n: number) {
  return n < currentStep.value
}

function canNext(): boolean {
  if (currentStep.value === 1) return !!selectedType.value
  if (currentStep.value === 2) {
    if (inputMode.value === 'batch') return selectedBatchIds.value.length > 0
    if (inputMode.value === 'data') return selectedProcessedIds.value.length > 0
    return !!customDir.value.trim()
  }
  if (currentStep.value === 3) return !!form.value.name
  return true
}

function next() {
  if (!canNext()) return
  if (currentStep.value < 4) currentStep.value++
}
function prev() {
  if (currentStep.value > 1) currentStep.value--
}

// 路径选择（弹窗）
async function pickCustomDir() {
  picking.value = true
  errorMsg.value = ''
  try {
    const res = await batchesApi.pickFolder()
    if (res.data?.cancelled) return
    const picked = res.data?.path
    if (!picked) {
      errorMsg.value = '未获取到所选路径'
      return
    }
    customDir.value = picked
  } catch (e: any) {
    errorMsg.value = e.message || '打开文件夹对话框失败'
  } finally {
    picking.value = false
  }
}

async function pickOutputPath() {
  picking.value = true
  errorMsg.value = ''
  try {
    const res = await batchesApi.pickFolder()
    if (res.data?.cancelled) return
    const picked = res.data?.path
    if (!picked) {
      errorMsg.value = '未获取到所选路径'
      return
    }
    // 转成相对项目根的路径（如果可能），便于跨设备迁移
    form.value.output_path = picked
  } catch (e: any) {
    errorMsg.value = e.message || '打开文件夹对话框失败'
  } finally {
    picking.value = false
  }
}

async function submit() {
  submitting.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    let input_paths: string[]
    if (inputMode.value === 'batch') {
      input_paths = selectedBatches.value.map((b) => b.image_folder_path)
    } else if (inputMode.value === 'data') {
      input_paths = selectedProcessedItems.value.map((p) => p.output_path)
    } else {
      input_paths = [customDir.value]
    }
    let taskId: string
    if (selectedType.value === 'clahe') {
      const res = await processingApi.submitClahe({
        name: form.value.name,
        input_paths,
        params: { clip_limit: form.value.clip_limit, grid_size: form.value.grid },
      })
      taskId = res.data.task_id
    } else {
      const res = await processingApi.submitCrop({
        name: form.value.name,
        input_paths,
        params: { tile_size: form.value.tile_size, overlap_ratio: form.value.overlap_ratio },
      })
      taskId = res.data.task_id
    }
    // 提交成功后跳转到任务详情
    router.push(`/process/tasks/${taskId}`)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.message || e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}

function typeBadge(_t: string) {
  return ''
}
function typeLabel(t: string) {
  return t === 'clahe' ? 'CLAHE 增强' : '滑窗裁切'
}
function statusBadge(s: string) {
  const x = (s || '').toLowerCase()
  if (x.includes('completed') || x.includes('完成')) return 'badge-success'
  if (x.includes('fail') || x.includes('错误')) return 'badge-error'
  if (x.includes('process') || x.includes('进行')) return 'badge-running'
  return 'badge-pending'
}

onMounted(async () => {
  try {
    const [batchesRes, processedRes] = await Promise.all([
      batchesApi.list(),
      processingApi.listProcessed().catch(() => null),
    ])
    batches.value = batchesRes.data.batches
    if (processedRes) processedItems.value = processedRes.data.items
  } catch {
    // 静默失败
  }
})
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/process/tasks" class="hover:text-brand-700">任务列表</router-link>
      <Icon name="chevron-right" :size="10" />
      <span class="text-ink-primary">新建任务</span>
    </div>
    <h1 class="text-2xl font-semibold text-ink-primary mb-1">新建处理任务</h1>
    <p class="text-sm text-ink-secondary mb-6">通过引导式向导创建 CLAHE 增强 / 滑窗裁切任务</p>

    <!-- 成功提示 -->
    <div v-if="successMsg" class="mb-5 bg-brand-50 border border-brand-300 rounded-card p-4 flex items-start gap-3">
      <Icon name="validate" :size="16" class="text-brand-700 mt-0.5" />
      <div class="flex-1">
        <div class="text-sm text-brand-700 font-medium">{{ successMsg }}</div>
        <router-link to="/process/tasks" class="mt-2 text-xs text-brand-700 hover:underline inline-flex items-center gap-1">
          <Icon name="arrow-left" :size="12" /> 返回任务列表
        </router-link>
      </div>
    </div>
    <div v-if="errorMsg" class="mb-5 bg-red-50 border border-red-200 rounded-card p-4 text-sm text-red-600 flex items-start gap-3">
      <Icon name="warning" :size="16" class="mt-0.5" />{{ errorMsg }}
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
        <!-- 步骤 1：选择类型 -->
        <div v-show="currentStep === 1" class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">选择处理类型</h2>
          <p class="text-xs text-ink-tertiary mb-5">根据处理目标选择对应的任务类型</p>
          <div class="grid grid-cols-2 gap-3">
            <div class="select-card" :class="{ selected: selectedType === 'clahe' }" @click="selectType('clahe')">
              <div class="flex items-center gap-2 mb-2">
                <Icon name="sparkle" :size="18" class="text-brand-700" />
                <div class="text-sm font-medium text-ink-primary">CLAHE 增强</div>
              </div>
              <div class="text-xs text-ink-tertiary leading-relaxed">对比度受限的自适应直方图均衡化 · 适合提升 UAV 图像细节</div>
            </div>
            <div class="select-card" :class="{ selected: selectedType === 'crop' }" @click="selectType('crop')">
              <div class="flex items-center gap-2 mb-2">
                <Icon name="grid" :size="18" class="text-ink-tertiary" />
                <div class="text-sm font-medium text-ink-primary">滑窗裁切</div>
              </div>
              <div class="text-xs text-ink-tertiary leading-relaxed">按固定尺寸滑窗裁切原图 · 命名带偏移便于回溯</div>
            </div>
          </div>
          <div class="mt-4 text-xs text-ink-tertiary flex items-center gap-1.5">
            <Icon name="info" :size="12" />
            标注校验、空标注清洗、子图坐标回推等标注处理不在本期范围，由外部标注工具完成。
          </div>
        </div>

        <!-- 步骤 2：输入源 -->
        <div v-show="currentStep === 2" class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">选择输入源</h2>
          <p class="text-xs text-ink-tertiary mb-5">支持单架次、多架次合并处理，或选择已有处理结果目录</p>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-2">输入源类型</label>
              <div class="grid grid-cols-3 gap-3">
                <div class="select-card !p-3.5" :class="{ selected: inputMode === 'batch' }" @click="inputMode = 'batch'">
                  <div class="flex items-start gap-2">
                    <Icon name="dataset" :size="18" class="text-brand-700 mt-0.5 flex-shrink-0" />
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-ink-primary">架次选择</div>
                      <div class="text-xs text-ink-tertiary mt-0.5">从已登记架次中合并处理</div>
                    </div>
                  </div>
                </div>
                <div class="select-card !p-3.5" :class="{ selected: inputMode === 'data' }" @click="inputMode = 'data'">
                  <div class="flex items-start gap-2">
                    <Icon name="augment" :size="18" class="text-amber-600 mt-0.5 flex-shrink-0" />
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-ink-primary">数据选择</div>
                      <div class="text-xs text-ink-tertiary mt-0.5">从加工产物 (output/) 中再加工</div>
                    </div>
                  </div>
                </div>
                <div class="select-card !p-3.5" :class="{ selected: inputMode === 'dir' }" @click="inputMode = 'dir'">
                  <div class="flex items-start gap-2">
                    <Icon name="folder-open" :size="18" class="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-ink-primary">自定义目录路径</div>
                      <div class="text-xs text-ink-tertiary mt-0.5">弹窗选择或手动输入任意目录</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="inputMode === 'batch'">
              <label class="block text-xs font-medium text-ink-primary mb-1.5">选择架次 <span class="text-red-500">*</span></label>
              <div class="border border-surface-border rounded-btn overflow-hidden">
                <table class="w-full text-sm">
                  <thead class="bg-surface-bg text-xs text-ink-secondary">
                    <tr>
                      <th class="text-left py-2 px-3 font-medium w-10">
                        <input
                          type="checkbox"
                          :checked="batches.length > 0 && selectedBatchIds.length === batches.length"
                          @change="toggleAll"
                          class="rounded accent-brand-700"
                        />
                      </th>
                      <th class="text-left py-2 px-3 font-medium">架次名称</th>
                      <th class="text-left py-2 px-3 font-medium">作物 / 地块</th>
                      <th class="text-right py-2 px-3 font-medium">原图数</th>
                      <th class="text-right py-2 px-3 font-medium">采集高度</th>
                    </tr>
                  </thead>
                  <tbody class="row-hover">
                    <tr v-if="batches.length === 0">
                      <td colspan="5" class="py-6 text-center text-ink-tertiary text-xs">暂无可选架次，请先在数据管理登记</td>
                    </tr>
                    <tr
                      v-for="b in batches"
                      :key="b.batch_id"
                      class="border-t border-surface-border"
                      :class="{ 'bg-brand-50/30': selectedBatchIds.includes(b.batch_id) }"
                    >
                      <td class="py-2 px-3">
                        <input
                          type="checkbox"
                          :checked="selectedBatchIds.includes(b.batch_id)"
                          @change="toggleBatch(b.batch_id)"
                          class="rounded accent-brand-700"
                        />
                      </td>
                      <td class="py-2 px-3 text-ink-primary font-medium">{{ b.batch_name }}</td>
                      <td class="py-2 px-3 text-ink-secondary text-xs">{{ b.crop_type }} · {{ b.plot_name || '-' }}</td>
                      <td class="text-right py-2 px-3 text-ink-secondary text-xs">{{ b.image_count }}</td>
                      <td class="text-right py-2 px-3 text-ink-secondary text-xs">{{ b.flight_altitude_m ? b.flight_altitude_m + ' m' : '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="text-xs text-ink-tertiary mt-1.5">
                已选 {{ selectedBatchIds.length }} 个架次 · 合计 {{ selectedImageCount }} 张原图 · 多架次合并处理时将统一输出
              </p>
            </div>

            <div v-else-if="inputMode === 'data'">
              <label class="block text-xs font-medium text-ink-primary mb-1.5">选择加工产物 <span class="text-red-500">*</span></label>
              <div class="border border-surface-border rounded-btn overflow-hidden">
                <table class="w-full text-sm">
                  <thead class="bg-surface-bg text-xs text-ink-secondary">
                    <tr>
                      <th class="text-left py-2 px-3 font-medium w-10"></th>
                      <th class="text-left py-2 px-3 font-medium">任务名</th>
                      <th class="text-left py-2 px-3 font-medium">类型</th>
                      <th class="text-right py-2 px-3 font-medium">图片数</th>
                      <th class="text-left py-2 px-3 font-medium">输出路径</th>
                      <th class="text-right py-2 px-3 font-medium">生成时间</th>
                    </tr>
                  </thead>
                  <tbody class="row-hover">
                    <tr v-if="processedItems.length === 0">
                      <td colspan="6" class="py-6 text-center text-ink-tertiary text-xs">暂无加工产物</td>
                    </tr>
                    <tr
                      v-for="p in processedItems"
                      :key="p.task_id"
                      class="border-t border-surface-border"
                      :class="{ 'bg-brand-50/30': selectedProcessedIds.includes(p.task_id) }"
                    >
                      <td class="py-2 px-3">
                        <input
                          type="checkbox"
                          :checked="selectedProcessedIds.includes(p.task_id)"
                          @change="toggleProcessed(p.task_id)"
                          class="rounded accent-brand-700"
                        />
                      </td>
                      <td class="py-2 px-3 text-ink-primary font-medium">{{ p.name }}</td>
                      <td class="py-2 px-3">
                        <span class="tag" :class="typeBadge(p.task_type)">{{ typeLabel(p.task_type) }}</span>
                      </td>
                      <td class="text-right py-2 px-3 text-ink-secondary text-xs">{{ p.image_count }}</td>
                      <td class="py-2 px-3 text-ink-tertiary font-mono text-[11px]">{{ p.output_path }}</td>
                      <td class="text-right py-2 px-3 text-ink-secondary text-xs">{{ p.created_at }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="text-xs text-ink-tertiary mt-1.5">
                已选 {{ selectedProcessedIds.length }} 个加工产物 · 合计 {{ selectedProcessedImageCount }} 张 · 将其作为下一轮处理的输入
              </p>
            </div>

            <div v-else>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">目录路径 <span class="text-red-500">*</span></label>
              <div class="flex gap-2">
                <div class="flex-1 relative">
                  <Icon name="folder-open" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
                  <input
                    v-model="customDir"
                    type="text"
                    placeholder="点击右侧「选择」按钮弹出系统文件夹选择对话框"
                    class="w-full pl-9 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300"
                  />
                </div>
                <button
                  @click="pickCustomDir"
                  :disabled="picking"
                  class="px-4 py-2 bg-white border border-surface-border hover:bg-surface-hover text-brand-700 rounded-btn text-sm font-medium inline-flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Icon name="folder-open" :size="14" /> {{ picking ? '选择中…' : '选择' }}
                </button>
              </div>
              <p class="text-xs text-ink-tertiary mt-1.5">单击「选择」会弹出系统文件夹选择窗口；也可直接键入路径</p>
            </div>
          </div>
        </div>

        <!-- 步骤 3：参数 -->
        <div v-show="currentStep === 3" class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">任务配置</h2>
          <p class="text-xs text-ink-tertiary mb-5">设置任务名称与运行时参数（根据处理类型动态展示）</p>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">任务名 <span class="text-red-500">*</span></label>
              <input
                v-model="form.name"
                type="text"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              />
            </div>
            <div v-if="selectedType === 'clahe'" class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">clipLimit</label>
                <input
                  v-model.number="form.clip_limit"
                  type="number"
                  step="0.1"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                />
                <p class="text-xs text-ink-tertiary mt-1.5">推荐 2.0 - 3.0</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">网格数量</label>
                <input
                  v-model="form.grid"
                  type="text"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                />
                <p class="text-xs text-ink-tertiary mt-1.5">如 8 × 8</p>
              </div>
            </div>
            <div v-else class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">切片尺寸 (tile_size)</label>
                <input
                  v-model.number="form.tile_size"
                  type="number"
                  step="32"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                />
                <p class="text-xs text-ink-tertiary mt-1.5">推荐 640</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">重叠率 (overlap_ratio)</label>
                <div class="flex items-center gap-2">
                  <input
                    v-model.number="form.overlap_ratio"
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm"
                  />
                  <span class="text-xs text-ink-tertiary">0-1</span>
                </div>
                <p class="text-xs text-ink-tertiary mt-1.5">默认 0.05</p>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">输出目录</label>
              <div class="flex gap-2">
                <div class="flex-1 relative">
                  <Icon name="folder-open" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
                  <input
                    v-model="form.output_path"
                    type="text"
                    class="w-full pl-9 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300"
                  />
                </div>
                <button
                  @click="pickOutputPath"
                  :disabled="picking"
                  class="px-4 py-2 bg-white border border-surface-border hover:bg-surface-hover text-brand-700 rounded-btn text-sm font-medium inline-flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Icon name="folder-open" :size="14" /> {{ picking ? '选择中…' : '选择' }}
                </button>
              </div>
              <p class="text-xs text-ink-tertiary mt-1.5">
                默认 <code class="px-1 py-0.5 bg-surface-hover rounded">output/</code> · 任务实际写入 <code class="px-1 py-0.5 bg-surface-hover rounded">output/{{ '{task_id}' }}/</code>
              </p>
            </div>
          </div>
        </div>

        <!-- 步骤 4：确认 -->
        <div v-show="currentStep === 4" class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">确认提交</h2>
          <p class="text-xs text-ink-tertiary mb-5">请核对以下任务配置，确认无误后提交</p>
          <div class="space-y-2.5 text-sm">
            <div class="flex justify-between"><span class="text-ink-tertiary">任务名</span><span class="text-ink-primary font-medium">{{ form.name }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">类型</span><span class="text-ink-primary">{{ selectedType === 'clahe' ? 'CLAHE 增强' : '滑窗裁切' }}</span></div>
            <div class="flex justify-between gap-2">
              <span class="text-ink-tertiary flex-shrink-0">输入源</span>
              <span class="text-ink-primary text-right text-xs">
                <template v-if="inputMode === 'batch'">
                  {{ selectedBatchIds.length }} 架次 · {{ selectedImageCount }} 张
                </template>
                <template v-else-if="inputMode === 'data'">
                  {{ selectedProcessedIds.length }} 个加工产物 · {{ selectedProcessedImageCount }} 张
                </template>
                <template v-else>
                  <span class="font-mono">{{ customDir }}</span>
                </template>
              </span>
            </div>
            <div v-if="selectedType === 'clahe'" class="flex justify-between"><span class="text-ink-tertiary">clipLimit / 网格</span><span class="text-ink-primary">{{ form.clip_limit }} / {{ form.grid }}</span></div>
            <div v-else class="flex justify-between"><span class="text-ink-tertiary">tile / overlap</span><span class="text-ink-primary">{{ form.tile_size }} / {{ form.overlap_ratio }}</span></div>
            <div class="flex justify-between gap-2">
              <span class="text-ink-tertiary flex-shrink-0">输出目录</span>
              <span class="text-ink-primary font-mono text-xs text-right break-all">{{ form.output_path }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 摘要侧栏 -->
      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">任务摘要</h3>
          <div class="space-y-2.5 text-xs">
            <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">任务名</span><span class="text-ink-primary font-medium text-right truncate">{{ form.name || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">类型</span><span class="text-ink-primary">{{ selectedType === 'clahe' ? 'CLAHE 增强' : selectedType === 'crop' ? '滑窗裁切' : '—' }}</span></div>
            <div class="flex justify-between gap-2">
              <span class="text-ink-tertiary flex-shrink-0">输入源</span>
              <span class="text-ink-primary text-right text-xs">
                <template v-if="inputMode === 'batch'">{{ selectedBatchIds.length }} 架次 · {{ selectedImageCount }} 张</template>
                <template v-else-if="inputMode === 'data'">{{ selectedProcessedIds.length }} 数据 · {{ selectedProcessedImageCount }} 张</template>
                <template v-else>自定义目录</template>
              </span>
            </div>
            <div v-if="selectedType === 'clahe'" class="flex justify-between"><span class="text-ink-tertiary">clipLimit</span><span class="text-ink-primary">{{ form.clip_limit }}</span></div>
            <div v-if="selectedType === 'crop'" class="flex justify-between"><span class="text-ink-tertiary">tile / overlap</span><span class="text-ink-primary">{{ form.tile_size }} / {{ form.overlap_ratio }}</span></div>
            <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">输出目录</span><span class="text-ink-primary font-mono text-[11px] text-right break-all">{{ form.output_path }}</span></div>
          </div>
          <div class="divider my-4"></div>
          <div class="flex gap-2">
            <router-link to="/process/tasks" class="flex-1 px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center">取消</router-link>
            <button v-if="currentStep > 1" @click="prev" class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary">上一步</button>
            <button
              v-if="currentStep < 4"
              @click="next"
              :disabled="!canNext()"
              class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-btn text-sm font-medium"
            >下一步</button>
            <button
              v-else
              @click="submit"
              :disabled="submitting"
              class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium"
            >{{ submitting ? '提交中…' : '提交任务' }}</button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
