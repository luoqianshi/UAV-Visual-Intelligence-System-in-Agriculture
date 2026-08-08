<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

// 区域分布热力图：8×8（可配置 N×N）网格计数，4 级色阶
// 1:1 迁移 V0.4 algo/counting.html 热力网格（稀疏/中等/密集/极密）
const props = withDefaults(
  defineProps<{
    data?: number[][]
    n?: number
  }>(),
  {
    data: () => [],
    n: 8,
  },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

// 浅色格子用深色文字，深色格子用白色文字（格子底色由 visualMap 控制）
function labelColorFor(v: number): string {
  return v <= 3 ? '#37352F' : '#ffffff'
}

// 将 number[][] 展平为 ECharts heatmap 数据项，按值定标签文字色
function buildSeriesData() {
  const n = props.n
  const out: Array<{ value: [number, number, number]; label: { color: string } }> = []
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const v = props.data?.[r]?.[c]
      const num = typeof v === 'number' ? v : 0
      out.push({
        value: [c, r, num],
        label: { color: labelColorFor(num) },
      })
    }
  }
  return out
}

function getOption(): echarts.EChartsCoreOption {
  const n = props.n
  const labels = Array.from({ length: n }, (_, i) => String(i + 1))
  return {
    tooltip: {
      formatter: (p: any) =>
        `区域 (${p.value[0] + 1}, ${p.value[1] + 1})<br/>计数：${p.value[2]} 株`,
    },
    grid: { left: 44, right: 16, top: 16, bottom: 64 },
    xAxis: {
      type: 'category',
      data: labels,
      name: '列',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { color: '#9B9A97', fontSize: 11 },
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#E9E9E7' } },
      axisTick: { show: false },
      axisLabel: { color: '#9B9A97', fontSize: 10 },
    },
    yAxis: {
      type: 'category',
      data: labels,
      name: '行',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { color: '#9B9A97', fontSize: 11 },
      // 反转：row 0 显示在顶部
      inverse: true,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: '#E9E9E7' } },
      axisTick: { show: false },
      axisLabel: { color: '#9B9A97', fontSize: 10 },
    },
    visualMap: {
      type: 'piecewise',
      min: 0,
      pieces: [
        { lte: 3, label: '稀疏 (0-3)', color: '#C8E6C9' },
        { gt: 3, lte: 6, label: '中等 (4-6)', color: '#81C784' },
        { gt: 6, lte: 9, label: '密集 (7-9)', color: '#4CAF50' },
        { gt: 9, label: '极密 (10+)', color: '#2F7D32' },
      ],
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 14,
      itemHeight: 14,
      textStyle: { color: '#787774', fontSize: 11 },
    },
    series: [
      {
        type: 'heatmap',
        data: buildSeriesData(),
        label: {
          show: true,
          fontSize: 10,
          formatter: (p: any) => String(p.value[2]),
        },
        emphasis: {
          itemStyle: { borderColor: '#2F7D32', borderWidth: 1 },
        },
      },
    ],
  }
}

function render() {
  if (!chart) return
  chart.setOption(getOption(), true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  if (el.value) {
    chart = echarts.init(el.value)
    render()
    window.addEventListener('resize', resize)
  }
})

watch(() => [props.data, props.n], render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div
    ref="el"
    class="w-full rounded-card border border-surface-border bg-white"
    style="height: 320px"
  ></div>
</template>
