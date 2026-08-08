<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import { useModelStore } from '@/stores/model'

// 注册模型页：1:1 迁移 algo/model-register.html，表单接入 registerModel
const router = useRouter()
const modelStore = useModelStore()

// 表单状态（classes 暂存为逗号字符串，提交时转数组）
const form = reactive({
  name: '',
  display_name: '',
  engine: 'ultralytics',
  category: 'sugarcane_seedling',
  weight: '',
  classes: 'Sugarcane Seedling',
  imgsz: 640,
  conf: 0.4,
  iou: 0.3,
  max_det: 300,
  device: 'auto',
  half: false,
})

const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

// 表单校验：name 与 weight 必填
const errors = computed(() => {
  const e: Record<string, string> = {}
  if (!form.name.trim()) e.name = 'name 为必填项'
  if (!form.weight.trim()) e.weight = 'weight 权重路径为必填项'
  return e
})

const classesArray = computed(() =>
  form.classes.split(',').map((s) => s.trim()).filter(Boolean),
)

// 注册摘要预览（匹配原型右侧摘要卡）
const summary = computed(() => ({
  name: form.name || '—',
  engine: form.engine,
  imgszConf: `${form.imgsz} / ${form.conf}`,
  deviceHalf: `${form.device} / ${form.half}`,
  classCount: classesArray.value.length,
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
      name: form.name.trim(),
      display_name: form.display_name.trim() || form.name.trim(),
      engine: form.engine,
      weight: form.weight.trim(),
      category: form.category.trim(),
      classes: classesArray.value,
      imgsz: Number(form.imgsz),
      conf: Number(form.conf),
      iou: Number(form.iou),
      max_det: Number(form.max_det),
      device: form.device,
      half: form.half,
    })
    successMsg.value = `模型「${form.name}」注册成功，即将返回列表…`
    setTimeout(() => router.push('/algo/models'), 800)
  } catch (e: any) {
    errorMsg.value = e?.message || '注册失败，请检查后端服务'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/algo/models" class="hover:text-brand-700">算法管理</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">注册模型</span>
    </div>
    <h1 class="text-2xl font-semibold text-ink-primary mb-1">注册新模型</h1>
    <p class="text-sm text-ink-secondary mb-4">将已训练好的权重动态注册到运行时模型注册中心（不持久化到 YAML），注册后可热切换激活</p>

    <SubTabs />

    <!-- 成功 / 错误提示 -->
    <div v-if="successMsg" class="mb-4 px-4 py-3 bg-brand-50 border border-brand-300 rounded-card text-sm text-brand-700 flex items-center gap-2">
      <i class="fa-solid fa-circle-check"></i>{{ successMsg }}
    </div>
    <div v-if="errorMsg" class="mb-4 px-4 py-3 bg-red-50 border border-red-300 rounded-card text-sm text-red-700 flex items-center gap-2">
      <i class="fa-solid fa-circle-exclamation"></i>{{ errorMsg }}
    </div>

    <div class="grid grid-cols-3 gap-5">
      <!-- 左栏：表单 -->
      <div class="col-span-2 space-y-5">
        <!-- 基础配置 -->
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
                  placeholder="yolov8s-sugarcane-v4"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300"
                />
                <p class="text-xs text-ink-tertiary mt-1.5">模型唯一标识</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">display_name</label>
                <input
                  v-model="form.display_name"
                  type="text"
                  placeholder="YOLOv8s 甘蔗幼苗 v4"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
                />
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-ink-primary mb-1.5">engine <span class="text-red-500">*</span></label>
                <select
                  v-model="form.engine"
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
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
                  class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300"
                />
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">weight <span class="text-red-500">*</span></label>
              <input
                v-model="form.weight"
                type="text"
                placeholder="models/yolov8s_sugarcane_v4.pt"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300"
              />
              <p class="text-xs text-ink-tertiary mt-1.5">权重文件路径（.pt，Ultralytics 格式）</p>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">classes <span class="text-red-500">*</span></label>
              <input
                v-model="form.classes"
                type="text"
                placeholder="Sugarcane Seedling"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300"
              />
              <p class="text-xs text-ink-tertiary mt-1.5">类别名称列表，多个用英文逗号分隔</p>
            </div>
          </div>
        </div>

        <!-- 推理参数 -->
        <div class="bg-white border border-surface-border rounded-card p-6">
          <h2 class="text-base font-semibold text-ink-primary mb-1">推理参数</h2>
          <p class="text-xs text-ink-tertiary mb-5">模型默认推理配置，运行时可在检测工作台覆盖</p>
          <div class="grid grid-cols-3 gap-4">
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">imgsz</label>
              <input
                v-model.number="form.imgsz"
                type="number"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">conf</label>
              <input
                v-model.number="form.conf"
                type="number"
                step="0.05"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">iou</label>
              <input
                v-model.number="form.iou"
                type="number"
                step="0.05"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">max_det</label>
              <input
                v-model.number="form.max_det"
                type="number"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">device</label>
              <select
                v-model="form.device"
                class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300"
              >
                <option value="auto">auto</option>
                <option value="cpu">cpu</option>
                <option value="cuda:0">cuda:0</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-ink-primary mb-1.5">half (FP16)</label>
              <label class="flex items-center gap-2 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm cursor-pointer h-[38px]">
                <input
                  v-model="form.half"
                  type="checkbox"
                  class="w-4 h-4 accent-brand-700"
                />
                <span class="text-ink-primary">{{ form.half ? 'true' : 'false' }}</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏：注册摘要 -->
      <div class="space-y-5">
        <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
          <h3 class="text-sm font-semibold text-ink-primary mb-3">注册摘要</h3>
          <div class="space-y-2.5 text-xs">
            <div class="flex justify-between">
              <span class="text-ink-tertiary">name</span>
              <span class="text-ink-primary font-mono">{{ summary.name }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-ink-tertiary">engine</span>
              <span class="text-ink-primary">{{ summary.engine }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-ink-tertiary">imgsz / conf</span>
              <span class="text-ink-primary">{{ summary.imgszConf }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-ink-tertiary">device / half</span>
              <span class="text-ink-primary">{{ summary.deviceHalf }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-ink-tertiary">类别数</span>
              <span class="text-ink-primary">{{ summary.classCount }}</span>
            </div>
          </div>
          <div class="divider my-4"></div>
          <div class="text-xs text-ink-tertiary mb-3">
            <i class="fa-solid fa-lightbulb text-amber-500 mr-1"></i>
            动态注册仅写入内存注册表，不持久化到 models.yaml；注册后可在模型库切换激活
          </div>
          <div class="flex gap-2">
            <router-link
              to="/algo/models"
              class="flex-1 px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center inline-flex items-center justify-center"
            >取消</router-link>
            <button
              :disabled="submitting"
              class="flex-1 px-3 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2"
              @click="onSubmit"
            >
              <i v-if="submitting" class="fa-solid fa-spinner fa-spin text-xs"></i>
              {{ submitting ? '注册中…' : '注册模型' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
