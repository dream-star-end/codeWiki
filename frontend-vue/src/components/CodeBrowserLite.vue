<template>
  <div class="code-browser-lite h-full flex flex-col">
    <!-- 顶部工具栏 -->
    <div class="flex items-center gap-2 px-4 py-2 bg-[var(--card-bg)] border-b border-[var(--border-color)]">
      <input
        v-model="fileSearch"
        type="text"
        placeholder="🔍 搜索文件..."
        class="input-japanese text-sm flex-1 py-1.5"
      />
      <button
        v-if="selectedFile"
        @click="explainCurrentFile"
        class="btn-japanese text-xs px-3 py-1.5"
        :disabled="explaining"
      >
        {{ explaining ? '🔄' : '💡' }} 解释文件
      </button>
      <button
        v-if="selectedFile"
        @click="copyCode"
        class="btn-japanese text-xs px-3 py-1.5"
      >
        📋 复制
      </button>
    </div>

    <div class="flex flex-1 min-h-0">
      <!-- 文件树侧边栏 -->
      <aside class="w-64 flex-shrink-0 bg-[var(--background)] border-r border-[var(--border-color)] overflow-y-auto">
        <div v-if="loading" class="p-4 text-center text-[var(--muted)]">
          <div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-primary)]"></div>
        </div>
        <div v-else-if="filteredTree" class="p-2">
          <FileTreeNodeLite
            :node="filteredTree"
            :selected-path="selectedFile"
            @select="selectFile"
          />
        </div>
        <div v-else class="p-4 text-center text-[var(--muted)] text-sm">
          暂无文件
        </div>
      </aside>

      <!-- 代码查看区 -->
      <main class="flex-1 flex flex-col overflow-hidden">
        <!-- 文件信息栏 -->
        <div v-if="selectedFile" class="flex items-center gap-3 px-4 py-2 bg-[var(--card-bg)] border-b border-[var(--border-color)]">
          <span class="text-sm font-mono text-[var(--foreground)] truncate flex-1">{{ selectedFile }}</span>
          <span v-if="fileContent" class="text-xs px-2 py-0.5 bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] rounded">
            {{ fileContent.language }}
          </span>
          <span v-if="fileContent" class="text-xs text-[var(--muted)]">
            {{ fileContent.lines }} 行
          </span>
        </div>

        <!-- 代码内容 -->
        <div class="flex-1 flex overflow-hidden">
          <!-- 符号大纲 -->
          <div
            v-if="showOutline && fileContent?.symbols?.length"
            class="w-48 flex-shrink-0 bg-[var(--background)] border-r border-[var(--border-color)] overflow-y-auto"
          >
            <div class="p-2">
              <div class="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-2 px-2">
                符号大纲
              </div>
              <div
                v-for="symbol in fileContent.symbols"
                :key="symbol.id"
                class="flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-xs hover:bg-[var(--accent-primary)]/10 transition-colors"
                :class="{ 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]': highlightedSymbol === symbol.id }"
                @click="jumpToSymbol(symbol)"
              >
                <span>{{ symbolIcon(symbol.kind) }}</span>
                <span class="truncate flex-1">{{ symbol.name }}</span>
                <span class="text-[var(--muted)]">:{{ symbol.line_start }}</span>
              </div>
            </div>
          </div>

          <!-- 代码区域 -->
          <div class="flex-1 flex flex-col overflow-hidden bg-[#1e1e1e]">
            <!-- 代码解释面板 -->
            <div
              v-if="fileExplanation"
              class="flex-shrink-0 max-h-48 overflow-y-auto p-4 bg-[var(--card-bg)] border-b border-[var(--border-color)]"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-semibold text-[var(--accent-primary)]">💡 文件解释</span>
                <button
                  @click="fileExplanation = ''"
                  class="text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
                >
                  关闭
                </button>
              </div>
              <div class="text-sm text-[var(--foreground)] prose-wiki" v-html="renderMarkdown(fileExplanation)"></div>
            </div>
            
            <!-- 代码内容 -->
            <div class="flex-1 overflow-auto">
              <div v-if="loadingFile" class="p-8 text-center">
                <div class="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--accent-primary)]"></div>
              </div>
              <pre
                v-else-if="fileContent"
                ref="codeRef"
                class="code-block p-4 m-0 font-mono text-sm leading-relaxed"
              ><code v-html="highlightedCode"></code></pre>
              <div v-else class="p-8 text-center text-[var(--muted)]">
                <div class="text-4xl mb-4">📄</div>
                <div class="text-sm">选择左侧文件查看代码</div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import FileTreeNodeLite from './FileTreeNodeLite.vue'

const props = defineProps<{
  repoId: string
  apiBase: string
  initialFile?: string
}>()

const emit = defineEmits<{
  (e: 'symbol-click', symbolId: string, filePath: string, line: number): void
  (e: 'file-select', path: string): void
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

// 代码解释
const explaining = ref(false)
const fileExplanation = ref('')

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
      return `<span class="line-num">${lineNum}</span><span class="line-code">${escaped}</span>`
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
    const res = await fetch(`${props.apiBase}/repos/${props.repoId}/files`)
    const data = await res.json()
    fileTree.value = data.tree
  } catch (err) {
    console.error('Failed to load file tree:', err)
  } finally {
    loading.value = false
  }
}

async function selectFile(path: string) {
  if (selectedFile.value === path) return
  selectedFile.value = path
  emit('file-select', path)
  await loadFileContent(path)
}

async function loadFileContent(path: string) {
  loadingFile.value = true
  try {
    const res = await fetch(`${props.apiBase}/repos/${props.repoId}/files/${encodeURIComponent(path)}`)
    if (res.ok) {
      fileContent.value = await res.json()
    } else {
      fileContent.value = null
    }
  } catch (err) {
    console.error('Failed to load file content:', err)
    fileContent.value = null
  } finally {
    loadingFile.value = false
  }
}

function jumpToSymbol(symbol: SymbolInfo) {
  highlightedSymbol.value = symbol.id
  emit('symbol-click', symbol.id, selectedFile.value, symbol.line_start)

  nextTick(() => {
    if (codeRef.value) {
      const lines = codeRef.value.querySelectorAll('.line-num')
      const targetLine = lines[symbol.line_start - 1]
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

// 解释当前文件
async function explainCurrentFile() {
  if (!selectedFile.value || explaining.value) return
  
  explaining.value = true
  fileExplanation.value = ''
  
  try {
    const res = await fetch(`${props.apiBase}/repos/${props.repoId}/explain/file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: selectedFile.value }),
    })
    
    if (res.ok) {
      const data = await res.json()
      fileExplanation.value = data.explanation || '无法生成解释'
    } else {
      fileExplanation.value = '解释生成失败'
    }
  } catch (err) {
    console.error('Failed to explain file:', err)
    fileExplanation.value = '解释生成失败'
  } finally {
    explaining.value = false
  }
}

// 渲染 Markdown
function renderMarkdown(content: string): string {
  // 简单的 markdown 渲染
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

// 公开方法供父组件调用
function openFile(path: string) {
  selectFile(path)
}

function scrollToLine(line: number) {
  nextTick(() => {
    if (codeRef.value) {
      const lines = codeRef.value.querySelectorAll('.line-num')
      const targetLine = lines[line - 1]
      if (targetLine) {
        targetLine.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  })
}

defineExpose({ openFile, scrollToLine })

watch(() => props.repoId, loadFileTree, { immediate: true })

watch(() => props.initialFile, (newFile) => {
  if (newFile && newFile !== selectedFile.value) {
    selectFile(newFile)
  }
})
</script>

<style scoped>
.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  min-height: 100%;
}

.code-block :deep(.line-num) {
  display: inline-block;
  width: 50px;
  padding-right: 16px;
  text-align: right;
  color: #6b7280;
  user-select: none;
  border-right: 1px solid #374151;
  margin-right: 16px;
}

.code-block :deep(.line-code) {
  white-space: pre;
}
</style>
