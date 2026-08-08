<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

// 置信度分布柱状图：高 ≥0.7 / 中 0.4-0.7 / 低 <0.4
// 1:1 迁移 V0.4 algo/counting.html 置信度分布区块（改为 ECharts 柱状图）
const props = withDefaults(
  defineProps<{
    dist?: { high: number; mid: number; low: number }
  }>(),
  {
    dist: () => ({ high: 0, mid: 0, low: 0 }),
  },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function getOption(): echarts.EChartsCoreOption {
  const d = props.dist || { high: 0, mid: 0, low: 0 }
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (p: any) => `${p[0].name}<br/>数量：${p[0].value} 株`,
    },
    grid: { left: 40, right: 20, top: 28, bottom: 28 },
    xAxis: {
      type: 'category',
      data: ['高 (≥0.7)', '中 (0.4-0.7)', '低 (<0.4)'],
      axisLine: { lineStyle: { color: '#E9E9E7' } },
      axisTick: { show: false },
      axisLabel: { color: '#787774', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#F1F1EF' } },
      axisLabel: { color: '#9B9A97', fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        barWidth: '46%',
        data: [
          { value: d.high, itemStyle: { color: '#2F7D32' } },
          { value: d.mid, itemStyle: { color: '#81C784' } },
          { value: d.low, itemStyle: { color: '#C8E6C9' } },
        ],
        label: {
          show: true,
          position: 'top',
          fontSize: 12,
          color: '#37352F',
          formatter: '{c}',
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

watch(() => props.dist, render, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" class="w-full" style="height: 240px"></div>
</template>
