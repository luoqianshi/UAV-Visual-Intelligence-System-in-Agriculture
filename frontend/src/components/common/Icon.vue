<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  name: string
  size?: number | string
  color?: string
  strokeWidth?: number
  spin?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 20,
  color: 'currentColor',
  strokeWidth: 1.7,
  spin: false,
})

const sizeStyle = computed(() => {
  const s = typeof props.size === 'number' ? `${props.size}px` : props.size
  return {
    width: s,
    height: s,
  }
})

// 图标路径数据 - 使用 xi-/fi- 系列自定义 SVG
const icons: Record<string, string> = {
  // 导航
  home: '<path d="M4.4 10.8 L12 4.5 L19.6 10.8"/><path d="M6.2 9.5 V19.5 H17.8 V9.5"/><path d="M10.2 19.5 V14.6 H13.8 V19.5"/>',
  dataset: '<path d="M12 3.6 L19.4 7.6 L12 11.6 L4.6 7.6 Z"/><path d="M4.6 12.1 L12 16.1 L19.4 12.1"/><path d="M4.6 16.3 L12 20.3 L19.4 16.3"/>',
  database: '<ellipse cx="12" cy="5.5" rx="7" ry="2.8"/><path d="M5 5.5 V12 A7 2.8 0 0 0 19 12 V5.5"/><path d="M5 12 V18.5 A7 2.8 0 0 0 19 18.5 V12"/>',
  augment: '<rect x="3.8" y="7.2" width="11.6" height="11.6" rx="1.8"/><path d="M5.8 15.8 L8.5 12.9 L10.4 14.8 L12.1 13.1 L13.6 14.6"/><path d="M18.6 3.8 L19.3 6 L21.5 6.7 L19.3 7.4 L18.6 9.6 L17.9 7.4 L15.7 6.7 L17.9 6 Z"/>',
  chip: '<rect x="7" y="7" width="10" height="10" rx="1.8"/><rect x="10.3" y="10.3" width="3.4" height="3.4" rx=".9"/><path d="M9.5 7 V4.6"/><path d="M14.5 7 V4.6"/><path d="M9.5 17 V19.4"/><path d="M14.5 17 V19.4"/><path d="M7 9.5 H4.6"/><path d="M7 14.5 H4.6"/><path d="M17 9.5 H19.4"/><path d="M17 14.5 H19.4"/>',
  nn: '<circle cx="12" cy="5.5" r="2.2"/><circle cx="5.5" cy="12" r="2.2"/><circle cx="18.5" cy="12" r="2.2"/><circle cx="12" cy="18.5" r="2.2"/><path d="M7.2 10.5 L10.3 7.2"/><path d="M16.8 10.5 L13.7 7.2"/><path d="M7.2 13.5 L10.3 16.8"/><path d="M16.8 13.5 L13.7 16.8"/>',
  gear: '<circle cx="12" cy="12" r="5.3"/><circle cx="12" cy="12" r="1.9"/><path d="M18.6 12 H20.4"/><path d="M5.4 12 H3.6"/><path d="M12 18.6 V20.4"/><path d="M12 5.4 V3.6"/><path d="M16.7 16.7 L18 18"/><path d="M7.3 16.7 L6 18"/><path d="M16.7 7.3 L18 6"/><path d="M7.3 7.3 L6 6"/>',
  user: '<circle cx="12" cy="8" r="3.5"/><path d="M5.5 19.5 C5.5 16 8.4 13.5 12 13.5 C15.6 13.5 18.5 16 18.5 19.5"/>',

  // 算法子栏目
  cropdetect: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 12 L11 15 L16 8"/>',
  count: '<path d="M6.1 5.5 V18.5"/><path d="M9.5 5.5 V18.5"/><path d="M12.9 5.5 V18.5"/><path d="M16.3 5.5 V18.5"/><path d="M3.9 15.7 L18.5 8.3"/>',
  sparkle: '<path d="M12 3 L13.5 9 L19.5 10.5 L13.5 12 L12 18 L10.5 12 L4.5 10.5 L10.5 9 Z"/>',

  // 操作
  upload: '<path d="M12 15 V4.9"/><path d="M8.3 8.5 L12 4.8 L15.7 8.5"/><path d="M5 15.5 V18 A1.5 1.5 0 0 0 6.5 19.5 H17.5 A1.5 1.5 0 0 0 19 18 V15.5"/>',
  download: '<path d="M12 4.9 V15"/><path d="M8.3 11.4 L12 15.1 L15.7 11.4"/><path d="M5 15.5 V18 A1.5 1.5 0 0 0 6.5 19.5 H17.5 A1.5 1.5 0 0 0 19 18 V15.5"/>',
  export: '<path d="M14 4.5 H18.5 A1.5 1.5 0 0 1 20 6 V18 A1.5 1.5 0 0 1 18.5 19.5 H6 A1.5 1.5 0 0 1 4.5 18 V13.5"/><path d="M12 4.5 L16 8.5 L12 12.5"/><path d="M16 8.5 H8"/>',
  'file-code': '<path d="M14 3 H6 A1.5 1.5 0 0 0 4.5 4.5 V19.5 A1.5 1.5 0 0 0 6 21 H18 A1.5 1.5 0 0 0 19.5 19.5 V9 Z"/><path d="M14 3 V9 H20"/><path d="M10 13 L8 15 L10 17"/><path d="M14 13 L16 15 L14 17"/>',
  'file-excel': '<path d="M14 3 H6 A1.5 1.5 0 0 0 4.5 4.5 V19.5 A1.5 1.5 0 0 0 6 21 H18 A1.5 1.5 0 0 0 19.5 19.5 V9 Z"/><path d="M14 3 V9 H20"/><path d="M9 14 L11 17 L13 14"/><path d="M8.5 17 H13.5"/>',
  plus: '<path d="M12 5 V19"/><path d="M5 12 H19"/>',
  close: '<path d="M6 6 L18 18"/><path d="M18 6 L6 18"/>',

  // 状态与提示 - fill使用currentColor
  validate: '<rect x="5.6" y="4.9" width="12.8" height="15.4" rx="1.8"/><rect x="9.1" y="3.2" width="5.8" height="3.4" rx="1.1"/><path d="M9.1 13.7 L11.3 15.9 L15 11.8"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9 C9.5 7.5 10.6 6.5 12 6.5 C13.4 6.5 14.5 7.5 14.5 9 C14.5 10.5 13 10.8 12 12"/><circle cx="12" cy="16" r="1" fill="currentColor" stroke="none"/>',
  bell: '<path d="M6 8 A6 6 0 0 1 18 8 V13 L20 16 H4 L6 13 Z"/><path d="M10 19 A2 2 0 0 0 14 19"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11 V16"/><circle cx="12" cy="8" r="1" fill="currentColor" stroke="none"/>',
  warning: '<path d="M12 3 L21 20 H3 Z"/><path d="M12 10 V14"/><circle cx="12" cy="17" r="1" fill="currentColor" stroke="none"/>',
  spinner: '<path d="M12 3 A9 9 0 0 1 21 12"/>',

  // 结果卡片
  seedling: '<path d="M4.6 19.6 H19.4"/><path d="M12 19.6 V11.6"/><path d="M12 13.6 C12 10.1 9.5 8.2 6.3 8.3 C6.5 11.8 9.1 13.7 12 13.6"/><path d="M12 13.6 C12 10.1 14.5 8.2 17.7 8.3 C17.5 11.8 14.9 13.7 12 13.6"/>',
  cane: '<path d="M12 21 V5"/><path d="M9 8 C9 8 10 6 12 6 C14 6 15 8 15 8"/><path d="M8 12 C8 12 10 10 12 10 C14 10 16 12 16 12"/><path d="M8 16 C8 16 10 14 12 14 C14 14 16 16 16 16"/>',
  gauge: '<path d="M4.5 16.9 A7.5 7.5 0 1 1 19.5 16.9"/><path d="M12 15.1 L15.7 10.3"/><circle cx="12" cy="15.5" r="1.6" fill="currentColor" stroke="none"/>',
  'chart-area': '<path d="M4 19 L4 6 L9 11 L14 7 L20 13 L20 19 Z"/>',
  grid: '<rect x="4.4" y="4.4" width="6.5" height="6.5" rx="1.7"/><rect x="13.1" y="4.4" width="6.5" height="6.5" rx="1.7"/><rect x="4.4" y="13.1" width="6.5" height="6.5" rx="1.7"/><rect x="13.1" y="13.1" width="6.5" height="6.5" rx="1.7"/>',
  target: '<circle cx="12" cy="12" r="8.2"/><circle cx="12" cy="12" r="4.8"/><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>',
  'vector-square': '<rect x="4.5" y="4.5" width="15" height="15" rx="1.5"/><path d="M4.5 9 H19.5"/><path d="M9 4.5 V19.5"/>',

  // 区域标题
  'table-cells': '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 4 V20"/><path d="M4 12 H20"/>',
  ruler: '<path d="M4.4 8.3 L11.5 4.7 L19.6 7.3 L18.3 16.9 L8.7 19.5 Z"/><path d="M4.4 8.3 L12.3 12.7 L19.6 7.3"/><path d="M11.5 4.7 L12.3 12.7"/><path d="M12.3 12.7 L8.7 19.5"/>',
  wrench: '<path d="M14.7 6.3 A4 4 0 0 0 19 10.6 L12 17.6 L5 20 L7.4 13 Z"/>',
  tune: '<path d="M4 7 H11"/><path d="M17 7 H20"/><path d="M4 17 H13"/><path d="M19 17 H20"/><circle cx="14" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>',

  // 空状态
  'folder-open': '<path d="M4 7 A2 2 0 0 1 6 5 H10 L12 7 H18 A2 2 0 0 1 20 9 V17 A2 2 0 0 1 18 19 H6 A2 2 0 0 1 4 17 V7 Z"/><path d="M4 13 L7 10 H20"/>',
  calculator: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8 H16"/><path d="M8 12 H10"/><path d="M12 12 H14"/><circle cx="16" cy="12" r="1" fill="currentColor" stroke="none"/><path d="M8 16 H10"/><path d="M12 16 H14"/><circle cx="16" cy="16" r="1" fill="currentColor" stroke="none"/>',
  bolt: '<path d="M13 3 L5 14 H12 L11 21 L19 10 H12 Z"/>',
  'list-ul': '<path d="M8 6 H20"/><path d="M8 12 H20"/><path d="M8 18 H20"/><circle cx="4.5" cy="6" r="1.2" fill="currentColor" stroke="none"/><circle cx="4.5" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="4.5" cy="18" r="1.2" fill="currentColor" stroke="none"/>',

  // 导航箭头
  'chevron-right': '<path d="M9 6 L15 12 L9 18"/>',
  'chevron-left': '<path d="M15 6 L9 12 L15 18"/>',
  'arrow-left': '<path d="M19 12 H5"/><path d="M12 5 L5 12 L12 19"/>',
  'arrow-right': '<path d="M5 12 H19"/><path d="M12 5 L19 12 L12 19"/>',

  // 状态
  check: '<path d="M5 12 L10 17 L19 7"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M20.5 15.5 L16 11 L9 18 L4.5 14.5"/>',

  // 检测按钮和bolt
  'cloud-arrow-up': '<path d="M12 15 V7"/><path d="M9 10 L12 7 L15 10"/><path d="M7 18 A4 4 0 0 1 7 10 A5 5 0 0 1 17 10 A4 4 0 0 1 17 18 Z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M16.5 16.5 L21 21"/>',
}
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :style="sizeStyle"
    viewBox="0 0 24 24"
    fill="none"
    :stroke="color"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    :class="{ 'animate-spin-slow': spin }"
  >
    <g v-html="icons[name] || ''" />
  </svg>
</template>
