<template>
  <div class="code-browser">
    <div class="browser-layout">
      <!-- 文件树侧边栏 -->
      <aside class="file-tree-sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">📁 文件浏览器</div>
          <n-input
            v-model:value="fileSearch"
            placeholder="搜索文件..."
            size="small"
            clearable
            class="file-search"
          >
            <template #prefix>🔍</template>
          </n-input>
        </div>
        <div class="tree-container">
          <n-spin :show="loading">
            <div v-if="filteredTree" class="file-tree">
              <FileTreeNode
                :node="filteredTree"
                :selected-path="selectedFile"
                @select="selectFile"
              />
            </div>
            <n-empty v-else description="暂无文件" />
          </n-spin>
        </div>
      </aside>

      <!-- 代码查看区 -->
      <main class="code-viewer">
        <div v-if="selectedFile" class="viewer-header">
          <div class="file-info">
            <span class="file-path">{{ selectedFile }}</span>
            <n-tag v-if="fileContent" size="small" :bordered="false">
              {{ fileContent.language }}
            </n-tag>
            <n-tag v-if="fileContent" size="small" type="info" :bordered="false">
              {{ fileContent.lines }} 行
            </n-tag>
          </div>
          <div class="viewer-actions">
            <n-button size="small" quaternary @click="copyCode">
              📋 复制
            </n-button>
            <n-button size="small" quaternary @click="exportContext">
              📤 导出上下文
            </n-button>
          </div>
        </div>

        <div class="code-content">
          <n-spin :show="loadingFile">
            <div v-if="fileContent" class="code-wrapper">
              <!-- 符号大纲 -->
              <div v-if="showOutline && fileContent.symbols.length" class="outline-panel">
                <div class="outline-title">符号大纲</div>
                <div
                  v-for="symbol in fileContent.symbols"
                  :key="symbol.id"
                  class="outline-item"
                  :class="{ active: highlightedSymbol === symbol.id }"
                  @click="jumpToSymbol(symbol)"
                >
                  <span class="symbol-icon">{{ symbolIcon(symbol.kind) }}</span>
                  <span class="symbol-name">{{ symbol.name }}</span>
                  <span class="symbol-line">:{{ symbol.line_start }}</span>
                </div>
              </div>

              <!-- 代码区 -->
              <div class="code-area">
                <pre class="code-block" ref="codeRef"><code v-html="highlightedCode"></code></pre>
              </div>
            </div>
            <div v-else class="empty-state">
              <div class="empty-icon">📄</div>
              <div class="empty-text">选择左侧文件查看代码</div>
            </div>
          </n-spin>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { NInput, NButton, NTag, NSpin, NEmpty } from 'naive-ui'
import { apiClient } from '../services/api'
import FileTreeNode from './FileTreeNode.vue'

const props = defineProps<{
  repoId: string
  apiBase: string
}>()

const emit = defineEmits<{
  (e: 'symbol-click', symbolId: string): void
  (e: 'export-context', files: string[]): void
}>()

interface FileNode {
  name: string
  path: string
  is_dir: boolean
  children?: FileNode[]
  language?: string
  size?: number
}

interface SymbolInfo {
  id: string
  name: string
  kind: string
  line_start: number
  line_end: number
  signature?: string
}

interface FileContent {
  path: string
  content: string
  language: string
  lines: number
  size: number
  symbols: SymbolInfo[]
}

const loading = ref(false)
const loadingFile = ref(false)
const fileTree = ref<FileNode | null>(null)
const selectedFile = ref('')
const fileContent = ref<FileContent | null>(null)
const fileSearch = ref('')
const showOutline = ref(true)
const highlightedSymbol = ref('')
const codeRef = ref<HTMLPreElement | null>(null)

const filteredTree = computed(() => {
  if (!fileTree.value) return null
  if (!fileSearch.value.trim()) return fileTree.value

  const query = fileSearch.value.toLowerCase()

  function filterNode(node: FileNode): FileNode | null {
    if (!node.is_dir) {
      return node.name.toLowerCase().includes(query) || node.path.toLowerCase().includes(query)
        ? node
        : null
    }

    const filteredChildren = node.children
      ?.map(filterNode)
      .filter((n): n is FileNode => n !== null)

    if (filteredChildren && filteredChildren.length > 0) {
      return { ...node, children: filteredChildren }
    }

    return null
  }

  return filterNode(fileTree.value)
})

const highlightedCode = computed(() => {
  if (!fileContent.value) return ''
  const lines = fileContent.value.content.split('\n')
  return lines
    .map((line, index) => {
      const lineNum = index + 1
      const escaped = escapeHtml(line)
      return `<span class="line-number">${lineNum}</span><span class="line-content">${escaped}</span>`
    })
    .join('\n')
})

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function symbolIcon(kind: string): string {
  const icons: Record<string, string> = {
    class: '🔷',
    function: '🔶',
    method: '🔸',
    variable: '📌',
    import: '📦',
  }
  return icons[kind] || '•'
}

async function loadFileTree() {
  if (!props.repoId) return
  loading.value = true
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/files`)
    fileTree.value = res.data.tree
  } catch (err) {
    console.error('Failed to load file tree:', err)
  } finally {
    loading.value = false
  }
}

async function selectFile(path: string) {
  if (selectedFile.value === path) return
  selectedFile.value = path
  await loadFileContent(path)
}

async function loadFileContent(path: string) {
  loadingFile.value = true
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/files/${encodeURIComponent(path)}`)
    fileContent.value = res.data
  } catch (err) {
    console.error('Failed to load file content:', err)
    fileContent.value = null
  } finally {
    loadingFile.value = false
  }
}

function jumpToSymbol(symbol: SymbolInfo) {
  highlightedSymbol.value = symbol.id
  emit('symbol-click', symbol.id)

  // 滚动到对应行
  nextTick(() => {
    if (codeRef.value) {
      const lineElements = codeRef.value.querySelectorAll('.line-number')
      const targetLine = lineElements[symbol.line_start - 1]
      if (targetLine) {
        targetLine.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  })
}

function copyCode() {
  if (fileContent.value) {
    navigator.clipboard.writeText(fileContent.value.content)
  }
}

function exportContext() {
  if (selectedFile.value) {
    emit('export-context', [selectedFile.value])
  }
}

watch(() => props.repoId, loadFileTree, { immediate: true })
</script>

<style scoped>
.code-browser {
  height: 100%;
  min-height: 500px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background: #ffffff;
}

.browser-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100%;
}

.file-tree-sidebar {
  background: var(--secondary-color);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-title {
  font-weight: 600;
  margin-bottom: 12px;
}

.file-search {
  width: 100%;
}

.tree-container {
  flex: 1;
  overflow: auto;
  padding: 8px;
}

.file-tree {
  font-size: 13px;
}

.code-viewer {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background: var(--secondary-color);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-path {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: #475569;
}

.viewer-actions {
  display: flex;
  gap: 8px;
}

.code-content {
  flex: 1;
  overflow: auto;
}

.code-wrapper {
  display: flex;
  height: 100%;
}

.outline-panel {
  width: 200px;
  background: var(--secondary-color);
  border-right: 1px solid var(--border-color);
  overflow: auto;
  padding: 12px;
}

.outline-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.outline-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.outline-item:hover {
  background: rgba(37, 99, 235, 0.08);
}

.outline-item.active {
  background: rgba(37, 99, 235, 0.15);
  color: var(--primary-color);
}

.symbol-icon {
  font-size: 12px;
}

.symbol-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.symbol-line {
  color: #94a3b8;
  font-size: 11px;
}

.code-area {
  flex: 1;
  overflow: auto;
}

.code-block {
  margin: 0;
  padding: 16px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #1e1e1e;
  color: #d4d4d4;
  min-height: 100%;
}

.code-block :deep(.line-number) {
  display: inline-block;
  width: 50px;
  padding-right: 16px;
  text-align: right;
  color: #6b7280;
  user-select: none;
  border-right: 1px solid #374151;
  margin-right: 16px;
}

.code-block :deep(.line-content) {
  white-space: pre;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #64748b;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 14px;
}

@media (max-width: 1024px) {
  .browser-layout {
    grid-template-columns: 1fr;
  }

  .file-tree-sidebar {
    max-height: 300px;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .outline-panel {
    display: none;
  }
}
</style>
