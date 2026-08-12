<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
import Icon from '@/components/common/Icon.vue'
import { batchesApi } from '@/api/batches'
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

const CUSTOM_CROPS_KEY = 'uav_vis_custom_crops'

const router = useRouter()

const form = ref({
  batch_name: '',
  crop_type: '甘蔗',
  flight_date: new Date().toISOString().slice(0, 10),
  plot_name: '',
  drone_model: 'DJI Mavic 3 M',
  flight_altitude_m: 5,
  description: '',
})
const imagePath = ref('')
const overlapFront = ref(0.8)
const overlapSide = ref(0.7)

const submitting = ref(false)
const scanning = ref(false)
const picking = ref(false)
const successMsg = ref('')
const errorMsg = ref('')
const scanResult = ref<{ valid: boolean; image_count: number; total_size_bytes: number; formats: string[]; message?: string } | null>(null)

const cropOptions = ['甘蔗', '玉米', '小麦', '水稻']
const customCropOptions = ref<string[]>([])
const droneOptions = ['DJI Mavic 3 M', 'DJI Mavic 3', 'DJI Phantom 4 Pro', '其他']

const allCropOptions = computed(() => {
  const merged = [...cropOptions, ...customCropOptions.value]
  return Array.from(new Set(merged))
})

onMounted(() => {
  try {
    const raw = localStorage.getItem(CUSTOM_CROPS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        customCropOptions.value = parsed.filter((x) => typeof x === 'string' && x.trim())
      }
    }
  } catch {
    // 忽略损坏的 localStorage 数据
  }
})

watch(
  () => form.value.crop_type,
  (val) => {
    const v = (val || '').trim()
    if (!v) return
    if (allCropOptions.value.includes(v)) return
    customCropOptions.value = [...customCropOptions.value, v]
    try {
      localStorage.setItem(CUSTOM_CROPS_KEY, JSON.stringify(customCropOptions.value))
    } catch {
      // localStorage 可能已满或不可用，忽略
    }
  }
)

const canSubmit = computed(() =>
  form.value.batch_name && form.value.crop_type && form.value.flight_date &&
  imagePath.value && scanResult.value?.valid
)

async function doScan() {
  if (!imagePath.value) {
    errorMsg.value = '请输入图片文件夹路径'
    return
  }
  scanning.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const res = await batchesApi.scanPath(imagePath.value)
    const result = res.data
    scanResult.value = result
    if (!result.valid) {
      errorMsg.value = result.message || '路径无效'
    }
  } catch (e: any) {
    errorMsg.value = e.message || '扫描失败'
    scanResult.value = null
  } finally {
    scanning.value = false
  }
}

async function doPick() {
  picking.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    const res = await batchesApi.pickFolder()
    if (res.data?.cancelled) return
    const picked = res.data?.path
    if (!picked) {
      errorMsg.value = '未获取到所选路径'
      return
    }
    imagePath.value = picked
    await doScan()
  } catch (e: any) {
    errorMsg.value = e.message || '打开文件夹对话框失败'
  } finally {
    picking.value = false
  }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    const res = await batchesApi.create({
      ...form.value,
      image_folder_path: imagePath.value,
      overlap_front: overlapFront.value,
      overlap_side: overlapSide.value,
    })
    successMsg.value = '架次登记成功'
    const batchId = res.data.batch_id
    setTimeout(() => {
      router.push(`/data/batches/${batchId}`)
    }, 800)
  } catch (e: any) {
    errorMsg.value = e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  form.value = {
    batch_name: '', crop_type: '甘蔗', flight_date: new Date().toISOString().slice(0, 10),
    plot_name: '', drone_model: 'DJI Mavic 3 M', flight_altitude_m: 5, description: '',
  }
  imagePath.value = ''
  overlapFront.value = 0.8
  overlapSide.value = 0.7
  scanResult.value = null
  successMsg.value = ''
  errorMsg.value = ''
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 ** 3) return (bytes / (1024 ** 2)).toFixed(1) + ' MB'
  return (bytes / (1024 ** 3)).toFixed(2) + ' GB'
}
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/batches" class="hover:text-brand-700">数据管理 / 原始架次</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">登记新架次</span>
    </div>
    <h1 class="text-2xl font-semibold text-ink-primary mb-1">注册新架次</h1>
    <p class="text-sm text-ink-secondary mb-6">登记 UAV 采集架次元数据与本机图片文件夹路径，建立标准化的架次记录</p>

    <DataSubTabs />

    <!-- 成功提示 -->
    <div
      v-if="successMsg"
      class="mb-5 bg-brand-50 border border-brand-300 rounded-card p-4 flex items-start gap-3"
    >
      <i class="fa-solid fa-circle-check text-brand-700 mt-0.5"></i>
      <div class="flex-1">
        <div class="text-sm text-brand-700 font-medium">{{ successMsg }}</div>
        <div class="mt-2 flex gap-2">
          <router-link to="/data/batches" class="text-xs text-brand-700 hover:underline inline-flex items-center gap-1">
            <i class="fa-solid fa-arrow-left text-[10px]"></i> 返回列表
          </router-link>
          <button @click="resetForm" class="text-xs text-ink-secondary hover:text-brand-700">继续登记</button>
        </div>
      </div>
    </div>
    <!-- 错误提示 -->
    <div v-if="errorMsg" class="mb-5 bg-red-50 border border-red-200 rounded-card p-4 flex items-start gap-3">
      <i class="fa-solid fa-circle-exclamation text-red-600 mt-0.5"></i>
      <div class="text-sm text-red-600">{{ errorMsg }}</div>
    </div>

    <div class="grid grid-cols-3 gap-5">
      <div class="col-span-2 space-y-5">
        <!-- 基本信息 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">基本信息</h2>
          <p class="text-xs text-ink-tertiary mb-5">为架次命名并登记 UAV 采集参数</p>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">架次名称 <span class="text-red-500">*</span></label>
              <input v-model="form.batch_name" type="text" placeholder="如：sugarcane_20260805_5_001" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300" />
              <p class="text-xs text-ink-tertiary mt-1.5">建议格式：<code class="px-1 py-0.5 bg-surface-hover rounded">作物_采集日期_采集高度_编号</code></p>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">作物类型 <span class="text-red-500">*</span></label>
                <input
                  v-model="form.crop_type"
                  list="cropList"
                  type="text"
                  placeholder="选择或输入新作物"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
                />
                <datalist id="cropList">
                  <option v-for="c in allCropOptions" :key="c" :value="c" />
                </datalist>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">采集日期 <span class="text-red-500">*</span></label>
                <input v-model="form.flight_date" type="date" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">地块名称</label>
                <input v-model="form.plot_name" type="text" placeholder="如：A区" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">飞行高度（米）</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="form.flight_altitude_m" type="number" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">m</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 图片文件夹路径 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">图片文件夹路径</h2>
          <p class="text-xs text-ink-tertiary mb-5">输入本机存放该架次图片的文件夹绝对路径，系统将校验并扫描索引</p>
          <div class="flex gap-2">
            <div class="flex-1 relative">
              <Icon name="folder-open" :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
              <input v-model="imagePath" type="text" placeholder="如：D:/data/sugarcane_images" class="w-full pl-9 pr-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
            </div>
            <button @click="doPick" :disabled="picking" class="px-4 py-2 bg-white border border-surface-border hover:bg-surface-hover text-brand-700 rounded-btn text-sm font-medium inline-flex items-center gap-1.5">
              <Icon name="folder-open" :size="12" /> {{ picking ? '选择中…' : '选择' }}
            </button>
            <button @click="doScan" :disabled="scanning" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium inline-flex items-center gap-1.5">
              <Icon name="search" :size="12" /> {{ scanning ? '扫描中…' : '扫描' }}
            </button>
          </div>
          <p class="text-xs text-ink-tertiary mt-2 flex items-center gap-1.5">
            <Icon name="info" :size="12" />
            路径必须为本机绝对路径；支持 .jpg/.jpeg/.png/.bmp/.tif/.tiff；单架次 ≤2000 张，单张 ≤50MB
          </p>
          <div v-if="scanResult && scanResult.valid" class="mt-4 pt-4 border-t border-surface-border">
            <div class="flex items-center justify-between mb-3">
              <div class="text-xs font-medium text-ink-primary">扫描结果</div>
              <span class="text-xs text-brand-700 inline-flex items-center gap-1"><Icon name="validate" :size="12" /> 路径有效可读</span>
            </div>
            <div class="grid grid-cols-3 gap-3 mb-3">
              <div class="bg-surface-bg rounded-btn p-3"><div class="text-xs text-ink-tertiary">图片数量</div><div class="text-lg font-semibold text-ink-primary mt-0.5">{{ scanResult.image_count }}</div></div>
              <div class="bg-surface-bg rounded-btn p-3"><div class="text-xs text-ink-tertiary">总大小</div><div class="text-lg font-semibold text-ink-primary mt-0.5">{{ formatBytes(scanResult.total_size_bytes) }}</div></div>
              <div class="bg-surface-bg rounded-btn p-3"><div class="text-xs text-ink-tertiary">格式</div><div class="text-lg font-semibold text-ink-primary mt-0.5">{{ scanResult.formats.join('、') }}</div></div>
            </div>
          </div>
        </div>

        <!-- 采集设备与航摄参数 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">采集设备与航摄参数</h2>
          <p class="text-xs text-ink-tertiary mb-5">记录无人机型号与航摄重叠率（可选）</p>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">无人机型号</label>
              <select v-model="form.drone_model" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm">
                <option v-for="d in droneOptions" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">航向重叠率</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="overlapFront" type="number" step="0.05" min="0" max="1" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">0-1</span>
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">旁向重叠率</label>
                <div class="flex items-center gap-2">
                  <input v-model.number="overlapSide" type="number" step="0.05" min="0" max="1" class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm" />
                  <span class="text-xs text-ink-tertiary">0-1</span>
                </div>
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">描述</label>
              <textarea v-model="form.description" rows="2" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm resize-none focus:outline-none focus:border-brand-300"></textarea>
            </div>
          </div>
        </div>
      </div>

      <!-- 配置摘要 -->
      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">配置摘要</h3>
          <div class="space-y-2.5 text-xs">
            <div class="flex justify-between"><span class="text-ink-tertiary">架次名称</span><span class="text-ink-primary font-medium">{{ form.batch_name || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">作物类型</span><span class="text-ink-primary">{{ form.crop_type }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">采集日期</span><span class="text-ink-primary">{{ form.flight_date || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">地块名称</span><span class="text-ink-primary">{{ form.plot_name || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">飞行高度</span><span class="text-ink-primary">{{ form.flight_altitude_m }} m</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">机型</span><span class="text-ink-primary">{{ form.drone_model }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">航向/旁向</span><span class="text-ink-primary">{{ overlapFront }} / {{ overlapSide }}</span></div>
            <div class="border-t border-surface-border my-1.5"></div>
            <div class="flex justify-between gap-2"><span class="text-ink-tertiary flex-shrink-0">图片路径</span><span class="text-ink-primary font-mono text-[11px] text-right break-all">{{ imagePath || '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">图片数量</span><span class="text-ink-primary font-medium">{{ scanResult?.image_count ?? '—' }}</span></div>
            <div class="flex justify-between"><span class="text-ink-tertiary">总大小</span><span class="text-ink-primary">{{ scanResult ? formatBytes(scanResult.total_size_bytes) : '—' }}</span></div>
          </div>
          <div class="divider my-4"></div>
          <div class="text-xs text-ink-tertiary mb-3">
            <Icon name="info" :size="12" class="text-amber-500 inline" />
            提交后架次将进入"已接入"状态，原始图片保留在本机路径（不复制），可用于创建处理任务
          </div>
          <div class="flex gap-2">
            <router-link to="/data/batches" class="flex-1 px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center">取消</router-link>
            <button
              @click="submit"
              :disabled="!canSubmit || submitting"
              class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-btn text-sm font-medium"
            >{{ submitting ? '提交中…' : '注册架次' }}</button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
