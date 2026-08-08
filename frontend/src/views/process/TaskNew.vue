<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import { useMockStore } from '@/stores/mock'
import { ref, computed, onMounted } from 'vue'

// 1:1 迁移 process/task-new.html：4 步引导式向导（类型 → 输入源 → 参数 → 确认）
const store = useMockStore()

const steps = [
  { n: 1, label: '选择类型' },
  { n: 2, label: '选择输入源' },
  { n: 3, label: '配置参数' },
  { n: 4, label: '确认提交' },
]
const currentStep = ref(1)

const selectedType = ref<'clahe' | 'crop' | ''>('clahe')
const selectedBatchIds = ref<string[]>([])
const inputMode = ref<'batch' | 'dir'>('batch')
const customDir = ref('')

const form = ref({
  name: 'CLAHE 增强 v3',
  clip_limit: 2.0,
  grid: '8 × 8',
  tile_size: 640,
  overlap_ratio: 0.1,
  output_path: 'output/clahe_20260806_103000/',
})

const successMsg = ref('')
const errorMsg = ref('')
const submitting = ref(false)

const selectedBatches = computed(() =>
  store.batches.filter((b) => selectedBatchIds.value.includes(b.id)),
)
const selectedImageCount = computed(() =>
  selectedBatches.value.reduce((s, b) => s + (b.image_count || 0), 0),
)

function selectType(t: 'clahe' | 'crop') {
  selectedType.value = t
  if (t === 'clahe') {
    form.value.name = 'CLAHE 增强 v3'
    form.value.output_path = 'output/clahe_20260806_103000/'
  } else {
    form.value.name = '滑窗裁切 640/0.1'
    form.value.output_path = 'output/crop_20260806_103000/'
  }
}

function toggleBatch(bid: string) {
  const i = selectedBatchIds.value.indexOf(bid)
  if (i >= 0) selectedBatchIds.value.splice(i, 1)
  else selectedBatchIds.value.push(bid)
}
function toggleAll() {
  if (selectedBatchIds.value.length === store.batches.length) selectedBatchIds.value = []
  else selectedBatchIds.value = store.batches.map((b) => b.id)
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
  if (currentStep.value === 2) return inputMode.value === 'dir' ? !!customDir.value : selectedBatchIds.value.length > 0
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

async function submit() {
  submitting.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    // V1 演示模式：不持久化
    await new Promise((r) => setTimeout(r, 300))
    successMsg.value = '处理任务已创建（V1 演示模式）· 数据未持久化'
  } catch (e: any) {
    errorMsg.value = e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  store.fetchBatches().catch(() => {})
})
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/process/tasks" class="hover:text-brand-700">任务列表</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">新建任务</span>
    </div>
    <h1 class="text-2xl font-semibold text-ink-primary mb-1">新建处理任务</h1>
    <p class="text-sm text-ink-secondary mb-6">通过引导式向导创建 CLAHE 增强 / 滑窗裁切任务</p>

    <!-- 成功提示 -->
    <div v-if="successMsg" class="mb-5 bg-brand-50 border border-brand-300 rounded-card p-4 flex items-start gap-3">
      <i class="fa-solid fa-circle-check text-brand-700 mt-0.5"></i>
      <div class="flex-1">
        <div class="text-sm text-brand-700 font-medium">{{ successMsg }}</div>
        <router-link to="/process/tasks" class="mt-2 text-xs text-brand-700 hover:underline inline-flex items-center gap-1">
          <i class="fa-solid fa-arrow-left text-[10px]"></i> 返回任务列表
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
        <!-- 步骤 1：选择类型 -->
        <div v-show="currentStep === 1" class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">选择处理类型</h2>
          <p class="text-xs text-ink-tertiary mb-5">根据处理目标选择对应的任务类型</p>
          <div class="grid grid-cols-2 gap-3">
            <div class="select-card" :class="{ selected: selectedType === 'clahe' }" @click="selectType('clahe')">
              <div class="flex items-center gap-2 mb-2">
                <i class="fa-solid fa-sun text-brand-700 text-lg"></i>
                <div class="text-sm font-medium text-ink-primary">CLAHE 增强</div>
              </div>
              <div class="text-xs text-ink-tertiary leading-relaxed">对比度受限的自适应直方图均衡化 · 适合提升 UAV 图像细节</div>
            </div>
            <div class="select-card" :class="{ selected: selectedType === 'crop' }" @click="selectType('crop')">
              <div class="flex items-center gap-2 mb-2">
                <i class="fa-solid fa-table-cells text-ink-tertiary text-lg"></i>
                <div class="text-sm font-medium text-ink-primary">滑窗裁切</div>
              </div>
              <div class="text-xs text-ink-tertiary leading-relaxed">按固定尺寸滑窗裁切原图 · 命名带偏移便于回溯</div>
            </div>
          </div>
          <div class="mt-4 text-xs text-ink-tertiary flex items-center gap-1.5">
            <i class="fa-solid fa-circle-info"></i>
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
              <div class="grid grid-cols-2 gap-3">
                <div class="select-card !p-3.5" :class="{ selected: inputMode === 'batch' }" @click="inputMode = 'batch'">
                  <div class="flex items-start gap-2">
                    <i class="fa-solid fa-layer-group text-brand-700 mt-0.5"></i>
                    <div><div class="text-sm font-medium text-ink-primary">架次选择（可多选）</div><div class="text-xs text-ink-tertiary mt-0.5">从已登记架次中合并处理</div></div>
                  </div>
                </div>
                <div class="select-card !p-3.5" :class="{ selected: inputMode === 'dir' }" @click="inputMode = 'dir'">
                  <div class="flex items-start gap-2">
                    <i class="fa-solid fa-folder-tree text-ink-tertiary mt-0.5"></i>
                    <div><div class="text-sm font-medium text-ink-primary">自定义目录路径</div><div class="text-xs text-ink-tertiary mt-0.5">可选自 CLAHE 增强结果目录</div></div>
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
                      <th class="text-left py-2 px-3 font-medium w-10"><input type="checkbox" :checked="store.batches.length > 0 && selectedBatchIds.length === store.batches.length" @change="toggleAll" class="rounded" /></th>
                      <th class="text-left py-2 px-3 font-medium">架次名称</th>
                      <th class="text-left py-2 px-3 font-medium">作物 / 地块</th>
                      <th class="text-right py-2 px-3 font-medium">原图数</th>
                      <th class="text-right py-2 px-3 font-medium">采集高度</th>
                    </tr>
                  </thead>
                  <tbody class="row-hover">
                    <tr v-if="store.batches.length === 0"><td colspan="5" class="py-6 text-center text-ink-tertiary text-xs">暂无可选架次</td></tr>
                    <tr
                      v-for="b in store.batches"
                      :key="b.id"
                      class="border-t border-surface-border"
                      :class="{ 'bg-brand-50/30': selectedBatchIds.includes(b.id) }"
                    >
                      <td class="py-2 px-3"><input type="checkbox" :checked="selectedBatchIds.includes(b.id)" @change="toggleBatch(b.id)" class="rounded" /></td>
                      <td class="py-2 px-3 text-ink-primary font-medium">{{ b.name }}</td>
                      <td class="py-2 px-3 text-ink-secondary text-xs">{{ b.crop_type }} · {{ b.plot_id || b.location || '-' }}</td>
                      <td class="text-right py-2 px-3 text-ink-secondary text-xs">{{ b.image_count }}</td>
                      <td class="text-right py-2 px-3 text-ink-secondary text-xs">{{ b.altitude_m }} m</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="text-xs text-ink-tertiary mt-1.5">已选 {{ selectedBatchIds.length }} 个架次 · 合计 {{ selectedImageCount }} 张原图 · 多架次合并处理时将统一输出</p>
            </div>

            <div v-else>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">目录路径 <span class="text-red-500">*</span></label>
              <div class="relative">
                <i class="fa-solid fa-folder-open absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary text-sm"></i>
                <input v-model="customDir" type="text" placeholder="output/clahe_20251004_103000/" class="w-full pl-9 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
              </div>
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
              <input v-model="form.name" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
            </div>
            <div v-if="selectedType === 'clahe'" class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">clipLimit</label>
                <input v-model.number="form.clip_limit" type="number" step="0.1" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                <p class="text-xs text-ink-tertiary mt-1.5">推荐 2.0 - 3.0</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">网格数量</label>
                <input v-model="form.grid" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
              </div>
            </div>
            <div v-else class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">切片尺寸 (tile_size)</label>
                <input v-model.number="form.tile_size" type="number" step="32" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                <p class="text-xs text-ink-tertiary mt-1.5">推荐 640</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">重叠率 (overlap_ratio)</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="form.overlap_ratio" type="number" step="0.05" min="0" max="1" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">0-1</span>
                </div>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">输出目录</label>
              <input v-model="form.output_path" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono" />
              <p class="text-xs text-ink-tertiary mt-1.5">默认存放于项目根 output 下，按时间戳区分</p>
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
            <div class="flex justify-between"><span class="text-ink-tertiary">输入源</span><span class="text-ink-primary">{{ inputMode === 'batch' ? `${selectedBatchIds.length} 架次 · ${selectedImageCount} 张` : customDir }}</span></div>
            <div v-if="selectedType === 'clahe'" class="flex justify-between"><span class="text-ink-tertiary">clipLimit / 网格</span><span class="text-ink-primary">{{ form.clip_limit }} / {{ form.grid }}</span></div>
            <div v-else class="flex justify-between"><span class="text-ink-tertiary">tile / overlap</span><span class="text-ink-primary">{{ form.tile_size }} / {{ form.overlap_ratio }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">输出目录</span><span class="text-ink-primary font-mono text-xs">{{ form.output_path }}</span></div>
          </div>
          <div class="mt-4 bg-brand-50/50 border border-brand-100 rounded-btn p-3 text-xs text-ink-secondary flex items-start gap-2">
            <i class="fa-solid fa-circle-info text-brand-700 mt-0.5"></i>
            <span>V1 演示模式：提交后仅展示成功提示，不会真正执行处理或持久化任务记录。</span>
          </div>
        </div>
      </div>

      <!-- 摘要侧栏 -->
      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">任务摘要</h3>
          <div class="space-y-2.5 text-xs">
            <div class="flex justify-between"><span class="text-ink-tertiary">任务名</span><span class="text-ink-primary font-medium">{{ form.name || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">类型</span><span class="text-ink-primary">{{ selectedType === 'clahe' ? 'CLAHE 增强' : selectedType === 'crop' ? '滑窗裁切' : '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">输入源</span><span class="text-ink-primary">{{ inputMode === 'batch' ? `${selectedBatchIds.length} 架次 · ${selectedImageCount} 张` : '自定义目录' }}</span></div>
            <div v-if="selectedType === 'clahe'" class="flex justify-between"><span class="text-ink-tertiary">clipLimit</span><span class="text-ink-primary">{{ form.clip_limit }}</span></div>
            <div v-if="selectedType === 'crop'" class="flex justify-between"><span class="text-ink-tertiary">tile / overlap</span><span class="text-ink-primary">{{ form.tile_size }} / {{ form.overlap_ratio }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">输出目录</span><span class="text-ink-primary font-mono text-[11px]">{{ form.output_path }}</span></div>
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
