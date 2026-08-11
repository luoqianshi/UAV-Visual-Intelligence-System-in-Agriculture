<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import { useModelStore } from '@/stores/model'
import type { ModelConfig } from '@/api/models'
import Icon from '@/components/common/Icon.vue'

const route = useRoute()
const modelStore = useModelStore()

const modelName = computed(() => String(route.params.name || ''))

const model = computed<ModelConfig | undefined>(() =>
  modelStore.models.find((m) => m.name === modelName.value),
)

onMounted(async () => {
  if (modelStore.models.length === 0) {
    await modelStore.fetchModels()
  }
})

async function onSwitch() {
  if (!model.value) return
  try {
    await modelStore.switchModel(model.value.name)
  } catch (e) {
    // 静默处理
  }
}
</script>

<template>
  <AppLayout>
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/algo/models" class="hover:text-brand-700 transition-colors">算法管理</router-link>
      <Icon name="chevron-right" :size="10" />
      <span class="text-ink-primary">{{ modelName }}</span>
    </div>

    <div class="flex items-end justify-between mb-5">
      <div>
        <div class="flex items-center gap-3">
          <div
            class="w-11 h-11 rounded-btn flex items-center justify-center"
            :class="model?.is_active ? 'bg-brand-50' : 'bg-surface-bg'"
          >
            <Icon name="seedling" :size="22" :color="model?.is_active ? '#10B981' : '#9CA3AF'" />
          </div>
          <div>
            <h1 class="text-2xl font-bold text-ink-primary tracking-tight">{{ model?.display_name || modelName }}</h1>
            <p class="text-sm text-ink-secondary mt-1">
              {{ model ? `${model.engine} · ${model.name}` : '模型未找到' }}
            </p>
          </div>
        </div>
      </div>
      <router-link
        v-if="model"
        to="/algo/detect"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold inline-flex items-center gap-2 transition-colors"
      >
        <Icon name="bolt" :size="14" /> 一键推理
      </router-link>
    </div>

    <SubTabs />

    <div v-if="!model" class="bg-white border border-surface-border rounded-card p-12 text-center">
      <Icon name="warning" :size="40" class="text-ink-tertiary opacity-40 mb-3 mx-auto" />
      <p class="text-sm text-ink-secondary mb-5">未找到模型「{{ modelName }}」</p>
      <router-link
        to="/algo/models"
        class="inline-flex items-center gap-2 px-4 py-2 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold transition-colors"
      >
        <Icon name="arrow-left" :size="14" /> 返回列表
      </router-link>
    </div>

    <template v-else>
      <div class="grid grid-cols-6 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
          <div class="text-xs text-ink-tertiary">输入尺寸 imgsz</div>
          <div class="text-2xl font-bold text-brand-700 mt-1 font-numeric">{{ model.imgsz }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
          <div class="text-xs text-ink-tertiary">置信度 conf</div>
          <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">{{ model.conf }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
          <div class="text-xs text-ink-tertiary">IoU 阈值</div>
          <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">{{ model.iou }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
          <div class="text-xs text-ink-tertiary">最大检测 max_det</div>
          <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">{{ model.max_det }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
          <div class="text-xs text-ink-tertiary">推理设备</div>
          <div class="text-2xl font-bold text-ink-primary mt-1">{{ model.device || '自动' }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4 card-hover">
          <div class="text-xs text-ink-tertiary">类别数</div>
          <div class="text-2xl font-bold text-ink-primary mt-1 font-numeric">{{ model.classes.length }}</div>
        </div>
      </div>

      <div class="border-b border-surface-border mb-5 flex items-center gap-1 text-sm">
        <button class="px-4 py-2.5 border-b-2 border-brand-700 text-brand-700 font-semibold">概览</button>
        <router-link
          to="/algo/detect"
          class="px-4 py-2.5 border-b-2 border-transparent text-ink-secondary hover:text-ink-primary transition-colors"
        >推理测试</router-link>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <div class="col-span-2 space-y-5">
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">推理参数</h3>
            <div class="grid grid-cols-4 gap-4">
              <div>
                <div class="text-xs text-ink-tertiary mb-1">输入尺寸 imgsz</div>
                <div class="text-sm font-medium text-ink-primary font-numeric">{{ model.imgsz }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">置信度 conf</div>
                <div class="text-sm font-medium text-ink-primary font-numeric">{{ model.conf }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">IoU 阈值</div>
                <div class="text-sm font-medium text-ink-primary font-numeric">{{ model.iou }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">最大检测 max_det</div>
                <div class="text-sm font-medium text-ink-primary font-numeric">{{ model.max_det }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">推理设备</div>
                <div class="text-sm font-medium text-ink-primary">{{ model.device || '自动' }}</div>
              </div>
            </div>
            <div class="mt-4 pt-3 border-t border-surface-border text-xs text-ink-tertiary flex items-center gap-1.5">
              <Icon name="info" :size="13" class="text-brand-500 flex-shrink-0" />
              高分辨率图像将按 imgsz 分块检测，坐标映射回原图后执行全局 NMS。
            </div>
          </div>

          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">检测类别</h3>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="(c, i) in model.classes"
                :key="i"
                class="tag tag-green"
              >
                <span class="w-2 h-2 rounded-full bg-brand-500 mr-1"></span>{{ c }}
              </span>
              <span v-if="model.classes.length === 0" class="text-xs text-ink-tertiary">未配置类别</span>
            </div>
          </div>

          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">推理样例</h3>
            <div class="border border-dashed border-surface-border rounded-card py-12 text-center">
              <Icon name="image" :size="40" class="text-ink-tertiary opacity-30 mb-2 mx-auto" />
              <p class="text-sm text-ink-tertiary">暂无推理样例</p>
              <p class="text-xs text-ink-tertiary mt-1">前往「推理测试」上传图像以生成样例</p>
            </div>
          </div>
        </div>

        <div class="space-y-5">
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">模型信息</h3>
            <div class="space-y-3 text-xs">
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">名称 (name)</span>
                <span class="font-mono text-ink-primary">{{ model.name }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">显示名</span>
                <span class="text-ink-primary font-medium">{{ model.display_name }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">引擎 (engine)</span>
                <span class="text-ink-primary">{{ model.engine }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">类别 (category)</span>
                <span class="text-ink-primary">{{ model.category || '—' }}</span>
              </div>
              <div class="flex justify-between items-start gap-2">
                <span class="text-ink-tertiary flex-shrink-0">权重文件</span>
                <span class="font-mono text-ink-primary text-[11px] break-all text-right">{{ model.weight }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">类别列表</span>
                <span class="text-ink-primary text-right max-w-[160px] truncate" :title="model.classes.join(', ')">{{ model.classes.join(', ') || '—' }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">输入尺寸</span>
                <span class="text-ink-primary font-numeric">{{ model.imgsz }} × {{ model.imgsz }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">conf / iou</span>
                <span class="text-ink-primary font-numeric">{{ model.conf }} / {{ model.iou }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">device</span>
                <span class="text-ink-primary">{{ model.device || '自动' }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">max_det</span>
                <span class="text-ink-primary font-numeric">{{ model.max_det }}</span>
              </div>
              <div class="flex justify-between items-center pt-2 border-t border-surface-border">
                <span class="text-ink-tertiary">状态</span>
                <span v-if="model.is_active" class="badge badge-success">
                  <span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span> 已激活
                </span>
                <span v-else class="badge badge-info">已发布</span>
              </div>
            </div>
          </div>

          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">操作</h3>
            <div class="space-y-2">
              <button
                v-if="!model.is_active"
                class="w-full px-3 py-2.5 bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white rounded-btn text-sm font-semibold inline-flex items-center justify-center gap-2 transition-colors"
                @click="onSwitch"
              >
                <Icon name="bolt" :size="14" /> 激活此模型
              </button>
              <div
                v-else
                class="w-full px-3 py-2.5 bg-brand-50 border border-brand-200 text-brand-700 rounded-btn text-sm font-semibold inline-flex items-center justify-center gap-2"
              >
                <Icon name="check" :size="14" /> 当前已激活
              </div>
              <router-link
                to="/algo/models"
                class="w-full px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center inline-flex items-center justify-center gap-2 transition-colors font-medium"
              >
                <Icon name="arrow-left" :size="14" /> 返回列表
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AppLayout>
</template>
