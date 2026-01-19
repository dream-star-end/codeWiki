<template>
  <div class="mcp-generator">
    <div class="mcp-header">
      <div class="mcp-icon">🔌</div>
      <div class="mcp-title">
        <h3>MCP Server 生成器</h3>
        <p>自动生成 MCP Server，让 AI 可以直接查询和理解代码库</p>
      </div>
    </div>

    <div class="mcp-content">
      <!-- 工具列表 -->
      <div class="tools-section">
        <h4>可用工具</h4>
        <div class="tools-grid">
          <div v-for="tool in mcpTools" :key="tool.name" class="tool-card">
            <div class="tool-name">{{ tool.name }}</div>
            <div class="tool-desc">{{ tool.description }}</div>
          </div>
        </div>
      </div>

      <!-- 生成操作 -->
      <div class="generate-section">
        <h4>生成 MCP Server</h4>
        <div class="generate-options">
          <n-button class="generate-btn" type="primary" size="large" :loading="generating" @click="generateMCP">
            🚀 一键生成 MCP Server
          </n-button>
          <div class="generate-hint">生成后可在 Cursor/Claude Desktop 中使用</div>
        </div>
      </div>

      <!-- 生成结果 -->
      <div v-if="generatedFiles" class="result-section">
        <h4>✅ 生成成功</h4>
        <div class="files-list">
          <div class="file-item">
            <span class="file-icon">🐍</span>
            <span class="file-name">MCP Server</span>
            <span class="file-path">{{ generatedFiles.server_file }}</span>
            <n-button size="small" @click="downloadServerCode">下载</n-button>
          </div>
          <div class="file-item">
            <span class="file-icon">⚙️</span>
            <span class="file-name">Cursor 配置</span>
            <span class="file-path">{{ generatedFiles.cursor_config }}</span>
            <n-button size="small" @click="downloadCursorConfig">下载</n-button>
          </div>
          <div class="file-item">
            <span class="file-icon">🤖</span>
            <span class="file-name">Claude 配置</span>
            <span class="file-path">{{ generatedFiles.claude_config }}</span>
            <n-button size="small" @click="downloadClaudeConfig">下载</n-button>
          </div>
          <div class="file-item">
            <span class="file-icon">📖</span>
            <span class="file-name">使用说明</span>
            <span class="file-path">{{ generatedFiles.readme }}</span>
            <n-button size="small" @click="downloadReadme">下载</n-button>
          </div>
        </div>
      </div>

      <!-- 使用指南 -->
      <div class="guide-section">
        <h4>使用指南</h4>
        <n-tabs type="segment" animated>
          <n-tab-pane name="cursor" tab="Cursor">
            <div class="guide-content">
              <ol>
                <li>点击"一键生成 MCP Server"</li>
                <li>下载生成的 <code>mcp_server_*.py</code> 文件</li>
                <li>安装依赖：<code>pip install mcp httpx</code></li>
                <li>
                  将 Cursor 配置合并到：
                  <ul>
                    <li><strong>Windows:</strong> <code>%APPDATA%\Cursor\User\globalStorage\cursor.mcp\config.json</code></li>
                    <li><strong>macOS:</strong> <code>~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/config.json</code></li>
                  </ul>
                </li>
                <li>重启 Cursor</li>
                <li>AI 现在可以调用工具查询代码库了！</li>
              </ol>
            </div>
          </n-tab-pane>
          <n-tab-pane name="claude" tab="Claude Desktop">
            <div class="guide-content">
              <ol>
                <li>点击"一键生成 MCP Server"</li>
                <li>下载生成的 <code>mcp_server_*.py</code> 文件</li>
                <li>安装依赖：<code>pip install mcp httpx</code></li>
                <li>
                  将 Claude 配置合并到：
                  <ul>
                    <li><strong>Windows:</strong> <code>%APPDATA%\Claude\claude_desktop_config.json</code></li>
                    <li><strong>macOS:</strong> <code>~/Library/Application Support/Claude/claude_desktop_config.json</code></li>
                  </ul>
                </li>
                <li>重启 Claude Desktop</li>
                <li>在对话中 Claude 可以使用工具查询代码库</li>
              </ol>
            </div>
          </n-tab-pane>
        </n-tabs>
      </div>

      <!-- 代码预览 -->
      <div class="preview-section">
        <div class="preview-header">
          <h4>Server 代码预览</h4>
          <n-button size="small" @click="loadServerCode" :loading="loadingCode">
            {{ serverCode ? '刷新' : '加载预览' }}
          </n-button>
        </div>
        <div v-if="serverCode" class="code-preview">
          <pre><code>{{ serverCodePreview }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NButton, NTabs, NTabPane } from 'naive-ui'
import { apiClient } from '../services/api'

const props = defineProps<{
  repoId: string
  apiBase: string
}>()

interface MCPTool {
  name: string
  description: string
  input_schema: any
}

interface GeneratedFiles {
  server_file: string
  cursor_config: string
  claude_config: string
  readme: string
}

const mcpTools = ref<MCPTool[]>([])
const generating = ref(false)
const generatedFiles = ref<GeneratedFiles | null>(null)
const serverCode = ref('')
const loadingCode = ref(false)

const serverCodePreview = computed(() => {
  if (!serverCode.value) return ''
  // 只显示前 80 行
  const lines = serverCode.value.split('\n')
  if (lines.length > 80) {
    return lines.slice(0, 80).join('\n') + '\n\n... (代码已截断)'
  }
  return serverCode.value
})

async function loadTools() {
  if (!props.repoId) return
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/mcp/tools`)
    mcpTools.value = res.data.tools
  } catch (err) {
    console.error('Failed to load MCP tools:', err)
  }
}

async function generateMCP() {
  if (!props.repoId) return
  generating.value = true
  try {
    const client = apiClient(props.apiBase)
    const res = await client.post(`/repos/${props.repoId}/mcp/generate`)
    generatedFiles.value = res.data.files
  } catch (err) {
    console.error('Failed to generate MCP:', err)
  } finally {
    generating.value = false
  }
}

async function loadServerCode() {
  if (!props.repoId) return
  loadingCode.value = true
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/mcp/server-code`)
    serverCode.value = res.data.code
  } catch (err) {
    console.error('Failed to load server code:', err)
  } finally {
    loadingCode.value = false
  }
}

async function downloadServerCode() {
  if (!props.repoId) return
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/mcp/server-code`)
    downloadFile(res.data.filename, res.data.code)
  } catch (err) {
    console.error('Failed to download:', err)
  }
}

async function downloadCursorConfig() {
  if (!props.repoId) return
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/mcp/cursor-config`)
    downloadFile(`cursor_config_${props.repoId}.json`, JSON.stringify(res.data.config, null, 2))
  } catch (err) {
    console.error('Failed to download:', err)
  }
}

async function downloadClaudeConfig() {
  if (!props.repoId) return
  try {
    const client = apiClient(props.apiBase)
    const res = await client.get(`/repos/${props.repoId}/mcp/claude-config`)
    downloadFile(`claude_config_${props.repoId}.json`, JSON.stringify(res.data.config, null, 2))
  } catch (err) {
    console.error('Failed to download:', err)
  }
}

async function downloadReadme() {
  // README 需要从生成的文件中读取，这里简化处理
  const readme = `# MCP Server 使用说明

请参考生成目录中的 README 文件获取完整使用说明。
`
  downloadFile(`README_${props.repoId}.md`, readme)
}

function downloadFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
}

onMounted(() => {
  loadTools()
})
</script>

<style scoped>
.mcp-generator {
  padding: 24px;
}

.mcp-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 2px solid var(--border-color);
}

.mcp-icon {
  width: 64px;
  height: 64px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 32px;
}

.mcp-title h3 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 4px;
  color: #1e293b;
}

.mcp-title p {
  color: #64748b;
  font-size: 0.95rem;
}

.mcp-content h4 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #334155;
  margin-bottom: 16px;
}

.tools-section {
  margin-bottom: 32px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.tool-card {
  background: var(--secondary-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  transition: all 0.2s;
}

.tool-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.tool-name {
  font-family: 'Fira Code', monospace;
  font-weight: 600;
  color: var(--primary-color);
  margin-bottom: 8px;
  font-size: 0.9rem;
}

.tool-desc {
  color: #64748b;
  font-size: 0.85rem;
  line-height: 1.5;
}

.generate-section {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1));
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
  text-align: center;
}

.generate-options {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.generate-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  border: none !important;
  font-size: 1rem;
  padding: 0 32px;
  height: 48px;
}

.generate-hint {
  color: #64748b;
  font-size: 0.85rem;
}

.result-section {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
}

.result-section h4 {
  color: #16a34a;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.file-icon {
  font-size: 20px;
}

.file-name {
  font-weight: 600;
  min-width: 120px;
}

.file-path {
  flex: 1;
  color: #64748b;
  font-size: 0.85rem;
  font-family: 'Fira Code', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.guide-section {
  margin-bottom: 32px;
}

.guide-content {
  padding: 16px;
  background: var(--secondary-color);
  border-radius: 12px;
}

.guide-content ol {
  padding-left: 20px;
  line-height: 2;
}

.guide-content ul {
  padding-left: 20px;
  margin: 8px 0;
}

.guide-content code {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
}

.preview-section {
  margin-bottom: 32px;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.code-preview {
  background: #1e1e1e;
  border-radius: 12px;
  padding: 16px;
  max-height: 400px;
  overflow: auto;
}

.code-preview pre {
  margin: 0;
}

.code-preview code {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  color: #d4d4d4;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .tools-grid {
    grid-template-columns: 1fr;
  }

  .file-item {
    flex-wrap: wrap;
  }

  .file-path {
    width: 100%;
    order: 3;
    margin-top: 8px;
  }
}
</style>
