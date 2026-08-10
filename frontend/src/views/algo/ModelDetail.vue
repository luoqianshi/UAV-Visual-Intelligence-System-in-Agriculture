<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import SubTabs from '@/components/layout/SubTabs.vue'
import { useModelStore } from '@/stores/model'
import type { ModelConfig } from '@/api/models'

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
    // 静默：UI 以 currentModel 为准
  }
}
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/algo/models" class="hover:text-brand-700">算法管理</router-link>
      <i class="fa-solid fa-chevron-right text-[8px]"></i>
      <span class="text-ink-primary">{{ modelName }}</span>
    </div>

    <!-- 页头：图标 + 标题 + 一键推理 -->
    <div class="flex items-end justify-between mb-4">
      <div>
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-btn flex items-center justify-center"
            :class="model?.is_active ? 'bg-brand-50' : 'bg-surface-bg'"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              :stroke="model?.is_active ? '#10B981' : '#9CA3AF'"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M4.6 19.6 H19.4"/>
              <path d="M12 19.6 V11.6"/>
              <path d="M12 13.6 C12 10.1 9.5 8.2 6.3 8.3 C6.5 11.8 9.1 13.7 12 13.6"/>
              <path d="M12 13.6 C12 10.1 14.5 8.2 17.7 8.3 C17.5 11.8 14.9 13.7 12 13.6"/>
            </svg>
          </div>
          <div>
            <h1 class="text-2xl font-semibold text-ink-primary">{{ model?.display_name || modelName }}</h1>
            <p class="text-sm text-ink-secondary mt-1">
              {{ model ? `${model.engine} · ${model.name}` : '模型未找到' }}
            </p>
          </div>
        </div>
      </div>
      <router-link
        v-if="model"
        to="/algo/detect"
        class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2"
      >
        <i class="fa-solid fa-bolt text-xs"></i> 一键推理
      </router-link>
    </div>

    <SubTabs />

    <!-- 未找到模型空状态 -->
    <div v-if="!model" class="bg-white border border-surface-border rounded-card p-10 text-center">
      <i class="fa-solid fa-circle-exclamation text-3xl text-ink-tertiary opacity-40 mb-3 block"></i>
      <p class="text-sm text-ink-secondary mb-4">未找到模型「{{ modelName }}」</p>
      <router-link
        to="/algo/models"
        class="inline-flex items-center gap-2 px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium"
      >
        <i class="fa-solid fa-arrow-left text-xs"></i> 返回列表
      </router-link>
    </div>

    <template v-else>
      <!-- 配置指标卡片（由真实配置字段派生） -->
      <div class="grid grid-cols-6 gap-4 mb-5">
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">输入尺寸 imgsz</div>
          <div class="text-2xl font-semibold text-brand-700 mt-1">{{ model.imgsz }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">置信度 conf</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ model.conf }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">IoU 阈值</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ model.iou }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">最大检测 max_det</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ model.max_det }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">推理设备</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ model.device || '自动' }}</div>
        </div>
        <div class="bg-white border border-surface-border rounded-card p-4">
          <div class="text-xs text-ink-tertiary">类别数</div>
          <div class="text-2xl font-semibold text-ink-primary mt-1">{{ model.classes.length }}</div>
        </div>
      </div>

      <!-- 概览 / 推理测试 子标签 -->
      <div class="border-b border-surface-border mb-5 flex items-center gap-1 text-sm">
        <button class="px-4 py-2.5 border-b-2 border-brand-700 text-brand-700 font-medium">概览</button>
        <router-link
          to="/algo/detect"
          class="px-4 py-2.5 border-b-2 border-transparent text-ink-secondary hover:text-ink-primary"
        >推理测试</router-link>
      </div>

      <div class="grid grid-cols-3 gap-5">
        <!-- 左栏 -->
        <div class="col-span-2 space-y-5">
          <!-- 推理参数 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">推理参数</h3>
            <div class="grid grid-cols-4 gap-4">
              <div>
                <div class="text-xs text-ink-tertiary mb-1">输入尺寸 imgsz</div>
                <div class="text-sm font-medium text-ink-primary">{{ model.imgsz }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">置信度 conf</div>
                <div class="text-sm font-medium text-ink-primary">{{ model.conf }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">IoU 阈值</div>
                <div class="text-sm font-medium text-ink-primary">{{ model.iou }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">最大检测 max_det</div>
                <div class="text-sm font-medium text-ink-primary">{{ model.max_det }}</div>
              </div>
              <div>
                <div class="text-xs text-ink-tertiary mb-1">推理设备</div>
                <div class="text-sm font-medium text-ink-primary">{{ model.device || '自动' }}</div>
              </div>
            </div>
            <div class="mt-4 pt-3 border-t border-surface-border text-xs text-ink-tertiary flex items-center gap-1.5">
              <i class="fa-solid fa-circle-info"></i>
              高分辨率图像将按 imgsz 分块检测，坐标映射回原图后执行全局 NMS。
            </div>
          </div>

          <!-- 检测类别 -->
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

          <!-- 推理样例（空状态） -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-4">推理样例</h3>
            <div class="border border-dashed border-surface-border rounded-card py-12 text-center">
              <i class="fa-solid fa-image text-3xl text-ink-tertiary opacity-30 mb-2 block"></i>
              <p class="text-sm text-ink-tertiary">暂无推理样例</p>
              <p class="text-xs text-ink-tertiary mt-1">前往「推理测试」上传图像以生成样例</p>
            </div>
          </div>
        </div>

        <!-- 右栏 -->
        <div class="space-y-5">
          <!-- 模型信息 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">模型信息</h3>
            <div class="space-y-2.5 text-xs">
              <div class="flex justify-between">
                <span class="text-ink-tertiary">名称 (name)</span>
                <span class="font-mono text-ink-primary">{{ model.name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">显示名</span>
                <span class="text-ink-primary font-medium">{{ model.display_name }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">引擎 (engine)</span>
                <span class="text-ink-primary">{{ model.engine }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">类别 (category)</span>
                <span class="text-ink-primary">{{ model.category || '—' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">权重文件</span>
                <span class="font-mono text-ink-primary text-[11px] break-all text-right">{{ model.weight }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">类别列表</span>
                <span class="text-ink-primary text-right">{{ model.classes.join(', ') || '—' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">输入尺寸</span>
                <span class="text-ink-primary">{{ model.imgsz }} × {{ model.imgsz }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">conf / iou</span>
                <span class="text-ink-primary">{{ model.conf }} / {{ model.iou }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">device</span>
                <span class="text-ink-primary">{{ model.device || '自动' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-ink-tertiary">max_det</span>
                <span class="text-ink-primary">{{ model.max_det }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-ink-tertiary">状态</span>
                <span v-if="model.is_active" class="badge badge-success">
                  <span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span> 已激活
                </span>
                <span v-else class="badge badge-info">已发布</span>
              </div>
            </div>
          </div>

          <!-- 操作 -->
          <div class="bg-white border border-surface-border rounded-card p-5">
            <h3 class="text-sm font-semibold text-ink-primary mb-3">操作</h3>
            <div class="space-y-2">
              <button
                v-if="!model.is_active"
                class="w-full px-3 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center justify-center gap-2"
                @click="onSwitch"
              >
                <i class="fa-solid fa-bolt text-xs"></i> 激活此模型
              </button>
              <div
                v-else
                class="w-full px-3 py-2 bg-brand-50 border border-brand-300 text-brand-700 rounded-btn text-sm font-medium inline-flex items-center justify-center gap-2"
              >
                <i class="fa-solid fa-check text-xs"></i> 当前已激活
              </div>
              <router-link
                to="/algo/models"
                class="w-full px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary text-center inline-flex items-center justify-center gap-2"
              >
                <i class="fa-solid fa-arrow-left text-xs"></i> 返回列表
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AppLayout>
</template>
