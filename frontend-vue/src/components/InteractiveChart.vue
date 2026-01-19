<template>
  <div 
    class="interactive-chart-wrapper"
    :class="{ 'fullscreen': isFullscreen }"
  >
    <!-- 工具栏 -->
    <div class="chart-toolbar">
      <div class="toolbar-left">
        <button @click="zoomIn" class="tool-btn" title="放大">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"/>
          </svg>
        </button>
        <button @click="zoomOut" class="tool-btn" title="缩小">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7"/>
          </svg>
        </button>
        <button @click="resetZoom" class="tool-btn" title="重置">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
        </button>
        <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
      </div>
      <div class="toolbar-right">
        <button @click="toggleFullscreen" class="tool-btn" :title="isFullscreen ? '退出全屏' : '全屏'">
          <svg v-if="!isFullscreen" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>
    
    <!-- 图表容器 -->
    <div 
      ref="containerRef"
      class="chart-container"
      @mousedown="startDrag"
      @wheel="handleWheel"
      @dblclick="resetZoom"
    >
      <div 
        ref="chartRef"
        class="chart-content"
        :style="chartStyle"
        @click="handleChartClick"
      >
        <slot></slot>
      </div>
    </div>
    
    <!-- 提示信息 -->
    <div v-if="showHint" class="chart-hint">
      💡 滚轮缩放 · 拖拽移动 · 双击重置 · 点击节点跳转
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  moduleMap?: Map<string, string>
}>()

const emit = defineEmits<{
  (e: 'node-click', nodeId: string, nodeText: string): void
  (e: 'module-jump', moduleId: string): void
}>()

const containerRef = ref<HTMLElement | null>(null)
const chartRef = ref<HTMLElement | null>(null)

// 缩放和平移状态
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isFullscreen = ref(false)
const showHint = ref(true)

// 拖拽状态
let isDragging = false
let startX = 0
let startY = 0
let startTranslateX = 0
let startTranslateY = 0

const chartStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
  transformOrigin: 'center center',
}))

function zoomIn() {
  scale.value = Math.min(3, scale.value * 1.2)
}

function zoomOut() {
  scale.value = Math.max(0.3, scale.value / 1.2)
}

function resetZoom() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  if (!isFullscreen.value) {
    resetZoom()
  }
}

function handleWheel(event: WheelEvent) {
  event.preventDefault()
  
  const delta = event.deltaY > 0 ? 0.9 : 1.1
  const newScale = Math.max(0.3, Math.min(3, scale.value * delta))
  
  // 以鼠标位置为中心缩放
  if (containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    const mouseX = event.clientX - rect.left - rect.width / 2
    const mouseY = event.clientY - rect.top - rect.height / 2
    
    const scaleChange = newScale / scale.value
    translateX.value = mouseX - (mouseX - translateX.value) * scaleChange
    translateY.value = mouseY - (mouseY - translateY.value) * scaleChange
  }
  
  scale.value = newScale
}

function startDrag(event: MouseEvent) {
  // 忽略右键
  if (event.button !== 0) return
  
  // 检查是否点击了可交互元素
  const target = event.target as HTMLElement
  if (target.closest('.node') || target.closest('a') || target.closest('text')) {
    return
  }
  
  isDragging = true
  startX = event.clientX
  startY = event.clientY
  startTranslateX = translateX.value
  startTranslateY = translateY.value
  
  document.addEventListener('mousemove', doDrag)
  document.addEventListener('mouseup', stopDrag)
}

function doDrag(event: MouseEvent) {
  if (!isDragging) return
  
  translateX.value = startTranslateX + (event.clientX - startX)
  translateY.value = startTranslateY + (event.clientY - startY)
}

function stopDrag() {
  isDragging = false
  document.removeEventListener('mousemove', doDrag)
  document.removeEventListener('mouseup', stopDrag)
}

function handleChartClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  
  // 查找最近的节点元素
  const nodeElement = target.closest('.node') || 
                      target.closest('[id^="flowchart-"]') ||
                      target.closest('g[class*="node"]')
  
  if (nodeElement) {
    // 获取节点 ID 和文本
    const nodeId = nodeElement.getAttribute('id') || ''
    const textElement = nodeElement.querySelector('text, .nodeLabel, span')
    const nodeText = textElement?.textContent?.trim() || nodeId
    
    emit('node-click', nodeId, nodeText)
    
    // 尝试匹配模块
    if (props.moduleMap) {
      const normalizedText = nodeText.toLowerCase().replace(/\s+/g, '')
      
      // 遍历模块映射查找匹配
      for (const [key, moduleId] of props.moduleMap.entries()) {
        if (key.toLowerCase().includes(normalizedText) || 
            normalizedText.includes(key.toLowerCase())) {
          emit('module-jump', moduleId)
          return
        }
      }
    }
  }
}

// 隐藏提示
onMounted(() => {
  setTimeout(() => {
    showHint.value = false
  }, 5000)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', doDrag)
  document.removeEventListener('mouseup', stopDrag)
})
</script>

<style scoped>
.interactive-chart-wrapper {
  position: relative;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--card-bg);
}

.interactive-chart-wrapper.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  border-radius: 0;
}

.chart-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--background);
  border-bottom: 1px solid var(--border-color);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--card-bg);
  color: var(--foreground);
  cursor: pointer;
  transition: all 0.15s;
}

.tool-btn:hover {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
}

.zoom-level {
  font-size: 12px;
  color: var(--muted);
  margin-left: 8px;
  min-width: 40px;
}

.chart-container {
  overflow: hidden;
  cursor: grab;
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.chart-container:active {
  cursor: grabbing;
}

.chart-content {
  transition: transform 0.1s ease-out;
}

.chart-content :deep(.node) {
  cursor: pointer;
}

.chart-content :deep(.node:hover) {
  filter: brightness(1.1);
}

.chart-content :deep(.node rect),
.chart-content :deep(.node circle),
.chart-content :deep(.node polygon) {
  transition: all 0.15s;
}

.chart-content :deep(.node:hover rect),
.chart-content :deep(.node:hover circle),
.chart-content :deep(.node:hover polygon) {
  stroke: var(--accent-primary);
  stroke-width: 2px;
}

.chart-hint {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  font-size: 12px;
  border-radius: 16px;
  pointer-events: none;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-50%) translateY(10px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

.fullscreen .chart-container {
  height: calc(100vh - 44px);
}
</style>
