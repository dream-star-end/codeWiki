<template>
  <n-modal v-model:show="visible" preset="card" title="导出 Codebase 上下文" :style="{ width: '700px' }">
    <div class="exporter">
      <div class="export-options">
        <div class="option-group">
          <label class="option-label">导出格式</label>
          <n-radio-group v-model:value="exportFormat" name="format">
            <n-space>
              <n-radio value="cursor">Cursor/IDE 格式</n-radio>
              <n-radio value="markdown">Markdown</n-radio>
              <n-radio value="json">JSON</n-radio>
            </n-space>
          </n-radio-group>
        </div>

        <div class="option-group">
          <label class="option-label">导出范围</label>
          <n-radio-group v-model:value="exportScope" name="scope">
            <n-space>
              <n-radio value="full">完整仓库</n-radio>
              <n-radio value="module">指定模块</n-radio>
              <n-radio value="files">指定文件</n-radio>
            </n-space>
          </n-radio-group>
        </div>

        <div v-if="exportScope === 'files'" class="option-group">
          <label class="option-label">选择文件</label>
          <n-select
            v-model:value="selectedFiles"
            multiple
            filterable
            :options="fileOptions"
            placeholder="选择要导出的文件..."
          />
        </div>

        <div class="option-group">
          <label class="option-label">最大 Token 数</label>
          <n-slider
            v-model:value="maxTokens"
            :min="5000"
            :max="200000"
            :step="5000"
            :format-tooltip="(v: number) => `${(v / 1000).toFixed(0)}K tokens`"
          />
          <span class="token-hint">{{ (maxTokens / 1000).toFixed(0) }}K tokens</span>
        </div>

        <div class="option-group">
          <n-checkbox v-model:checked="includeSummary">包含项目摘要</n-checkbox>
        </div>
      </div>

      <div v-if="smartQuery" class="smart-context">
        <label class="option-label">智能上下文（基于问题）</label>
        <n-input
          v-model:value="contextQuery"
          type="textarea"
          placeholder="描述你要解决的问题，AI将智能选取相关代码..."
          :rows="3"
        />
        <n-button class="smart-btn" type="primary" :loading="loading" @click="generateSmartContext">
          生成智能上下文
        </n-button>
      </div>

      <div v-if="exportResult" class="export-result">
        <div class="result-header">
          <div class="result-stats">
            <span>📊 {{ exportResult.token_count.toLocaleString() }} tokens</span>
            <span>📁 {{ exportResult.files_included.length }} 个文件</span>
          </div>
          <n-space>
            <n-button size="small" @click="copyResult">📋 复制</n-button>
            <n-button size="small" @click="downloadResult">💾 下载</n-button>
          </n-space>
        </div>
        <div class="result-preview">
          <pre>{{ previewContent }}</pre>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button @click="visible = false">取消</n-button>
        <n-button type="primary" :loading="loading" @click="doExport">
          {{ smartQuery ? '导出' : '生成并导出' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  NModal,
  NRadioGroup,
  NRadio,
  NSpace,
  NSelect,
  NSlider,
  NCheckbox,
  NInput,
  NButton,
} from 'naive-ui'
import { apiClient } from '../services/api'

const props = defineProps<{
  modelValue: boolean
  repoId: string
  apiBase: string
  files?: string[]
  smartQuery?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

interface ExportResult {
  content: string
  token_count: number
  files_included: string[]
  format: string
}

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const exportFormat = ref<'cursor' | 'markdown' | 'json'>('cursor')
const exportScope = ref<'full' | 'module' | 'files'>('full')
const selectedFiles = ref<string[]>([])
const maxTokens = ref(50000)
const includeSummary = ref(true)
const contextQuery = ref('')
const exportResult = ref<ExportResult | null>(null)

const fileOptions = computed(() => {
  return (props.files || []).map((f) => ({ label: f, value: f }))
})

const previewContent = computed(() => {
  if (!exportResult.value) return ''
  const content = exportResult.value.content
  // 只显示前 2000 字符的预览
  if (content.length > 2000) {
    return content.slice(0, 2000) + '\n\n... (内容已截断，完整内容请下载)'
  }
  return content
})

async function doExport() {
  if (!props.repoId) return
  loading.value = true
  try {
    const client = apiClient(props.apiBase)
    const res = await client.post(`/repos/${props.repoId}/codebase/export`, {
      format: exportFormat.value,
      scope: exportScope.value,
      file_paths: exportScope.value === 'files' ? selectedFiles.value : null,
      max_tokens: maxTokens.value,
      include_summary: includeSummary.value,
    })
    exportResult.value = res.data
  } catch (err) {
    console.error('Export failed:', err)
  } finally {
    loading.value = false
  }
}

async function generateSmartContext() {
  if (!props.repoId || !contextQuery.value.trim()) return
  loading.value = true
  try {
    const client = apiClient(props.apiBase)
    const res = await client.post(`/repos/${props.repoId}/codebase/context`, {
      query: contextQuery.value,
      max_tokens: maxTokens.value,
    })
    exportResult.value = res.data
  } catch (err) {
    console.error('Smart context generation failed:', err)
  } finally {
    loading.value = false
  }
}

function copyResult() {
  if (exportResult.value) {
    navigator.clipboard.writeText(exportResult.value.content)
  }
}

function downloadResult() {
  if (!exportResult.value) return
  const ext = exportFormat.value === 'json' ? 'json' : exportFormat.value === 'markdown' ? 'md' : 'txt'
  const blob = new Blob([exportResult.value.content], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `codebase-context.${ext}`
  link.click()
}

watch(
  () => props.files,
  (files) => {
    if (files && files.length > 0) {
      selectedFiles.value = files
      exportScope.value = 'files'
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.exporter {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.export-options {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-label {
  font-weight: 600;
  font-size: 14px;
  color: #374151;
}

.token-hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.smart-context {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--secondary-color);
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.smart-btn {
  align-self: flex-start;
}

.export-result {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--secondary-color);
  border-bottom: 1px solid var(--border-color);
}

.result-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #475569;
}

.result-preview {
  max-height: 300px;
  overflow: auto;
  padding: 16px;
  background: #1e1e1e;
}

.result-preview pre {
  margin: 0;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
