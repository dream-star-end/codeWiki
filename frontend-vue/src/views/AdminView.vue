<template>
  <div class="min-h-screen paper-texture">
    <header class="sticky top-0 z-10 bg-[var(--card-bg)] border-b border-[var(--border-color)] shadow-custom">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <router-link to="/" class="text-[var(--accent-primary)] hover:text-[var(--highlight)] flex items-center gap-1 text-sm">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
          </svg>
          返回项目列表
        </router-link>
        <h1 class="text-lg font-bold text-[var(--accent-primary)]">管理员后台</h1>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <!-- Token Usage -->
      <section class="card-japanese p-6">
        <h2 class="text-lg font-semibold text-[var(--foreground)] mb-2">总 Token 消耗</h2>
        <p class="text-xs text-[var(--muted)] mb-4">包含 LLM 与 Embedding 调用（部分为估算值）</p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <p class="text-xs text-[var(--muted)]">总计</p>
            <div class="text-2xl font-bold text-[var(--accent-primary)]">
              {{ totalTokens.toLocaleString() }}
            </div>
          </div>
          <div>
            <p class="text-xs text-[var(--muted)]">LLM 输入 / 输出</p>
            <div class="text-lg font-semibold text-[var(--accent-primary)]">
              {{ llmPromptTokens.toLocaleString() }} / {{ llmCompletionTokens.toLocaleString() }}
            </div>
          </div>
          <div>
            <p class="text-xs text-[var(--muted)]">Embedding</p>
            <div class="text-lg font-semibold text-[var(--accent-primary)]">
              {{ embeddingTokens.toLocaleString() }}
            </div>
          </div>
        </div>
      </section>
      <!-- LLM Config -->
      <section class="card-japanese p-6">
        <h2 class="text-lg font-semibold text-[var(--foreground)] mb-4">全局 LLM 配置</h2>
        <p class="text-xs text-[var(--muted)] mb-3">用于生成文档和 AI 问答</p>
        <div v-if="llmStatus" class="mb-3 text-sm text-[var(--muted)]">
          当前状态：{{ llmStatus }}
        </div>
        <div v-if="llmTestStatus" class="mb-3 text-sm text-[var(--muted)]">
          检查结果：{{ llmTestStatus }}
        </div>
        <form @submit.prevent="saveConfig" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium mb-2">Base URL</label>
            <input v-model="config.base_url" class="input-japanese w-full" placeholder="https://api.example.com" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">模型名称</label>
            <input v-model="config.model_name" class="input-japanese w-full" placeholder="gpt-4 / glm-4.7" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">API Key</label>
            <input v-model="config.api_key" class="input-japanese w-full" placeholder="sk-***" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">超时时间 (秒)</label>
            <input v-model.number="config.timeout_s" type="number" class="input-japanese w-full" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">最大 tokens</label>
            <input v-model.number="config.max_tokens" type="number" class="input-japanese w-full" />
          </div>
          <div class="flex items-end gap-3">
            <button class="btn-japanese w-full" :disabled="llmSaving">保存配置</button>
            <button type="button" class="btn-japanese w-full" :disabled="llmTesting" @click="testLlmConfig">
              {{ llmTesting ? '检查中...' : '检查连接' }}
            </button>
          </div>
        </form>
      </section>

      <!-- Embedding Config -->
      <section class="card-japanese p-6">
        <h2 class="text-lg font-semibold text-[var(--foreground)] mb-4">Embedding 模型配置</h2>
        <p class="text-xs text-[var(--muted)] mb-3">用于 AI 问答的语义检索，不配置则使用哈希伪向量（检索质量较差）</p>
        <div v-if="embeddingStatus" class="mb-3 text-sm text-[var(--muted)]">
          当前状态：{{ embeddingStatus }}
        </div>
        <div v-if="embeddingTestStatus" class="mb-3 text-sm text-[var(--muted)]">
          检查结果：{{ embeddingTestStatus }}
        </div>
        <form @submit.prevent="saveEmbeddingConfig" class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium mb-2">Base URL</label>
            <input v-model="embeddingConfig.base_url" class="input-japanese w-full" placeholder="https://api.openai.com" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">模型名称</label>
            <input v-model="embeddingConfig.model_name" class="input-japanese w-full" placeholder="text-embedding-3-small" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">API Key</label>
            <input v-model="embeddingConfig.api_key" class="input-japanese w-full" placeholder="sk-***" />
          </div>
          <div class="flex items-end gap-3">
            <button class="btn-japanese w-full" :disabled="embeddingSaving">保存配置</button>
            <button type="button" class="btn-japanese w-full" :disabled="embeddingTesting" @click="testEmbeddingConfig">
              {{ embeddingTesting ? '检查中...' : '检查连接' }}
            </button>
          </div>
        </form>
        <div class="mt-4 p-3 bg-[var(--background)] rounded-lg text-xs text-[var(--muted)]">
          <p class="font-medium mb-1">常用 Embedding 模型：</p>
          <ul class="list-disc list-inside space-y-1">
            <li>OpenAI: <code>text-embedding-3-small</code> / <code>text-embedding-ada-002</code></li>
            <li>智谱 GLM: <code>embedding-3</code> (Base URL: https://open.bigmodel.cn/api/paas)</li>
          </ul>
        </div>
      </section>

      <!-- Users -->
      <section class="card-japanese p-6">
        <h2 class="text-lg font-semibold text-[var(--foreground)] mb-4">用户管理</h2>
        <div v-if="loading" class="text-sm text-[var(--muted)]">加载中...</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-[var(--muted)] border-b border-[var(--border-color)]">
                <th class="py-2">用户名</th>
                <th class="py-2">邮箱</th>
                <th class="py-2">角色</th>
                <th class="py-2">状态</th>
                <th class="py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id" class="border-b border-[var(--border-color)]">
                <td class="py-2">{{ u.username }}</td>
                <td class="py-2">{{ u.email }}</td>
                <td class="py-2">
                  <select v-model="u.role" class="input-japanese text-xs" @change="updateUser(u)">
                    <option value="admin">管理员</option>
                    <option value="user">普通用户</option>
                  </select>
                </td>
                <td class="py-2">
                  <label class="inline-flex items-center gap-2 text-xs">
                    <input type="checkbox" v-model="u.is_active" @change="updateUser(u)" />
                    {{ u.is_active ? '启用' : '禁用' }}
                  </label>
                </td>
                <td class="py-2">
                  <button class="text-xs text-[var(--highlight)] hover:underline" @click="removeUser(u.id)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiClient } from '../services/api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const client = apiClient(auth.apiBase)

const users = ref<any[]>([])
const loading = ref(false)
const llmStatus = ref('')
const embeddingStatus = ref('')
const totalTokens = ref(0)
const llmPromptTokens = ref(0)
const llmCompletionTokens = ref(0)
const embeddingTokens = ref(0)
const llmTestStatus = ref('')
const embeddingTestStatus = ref('')
const llmSaving = ref(false)
const embeddingSaving = ref(false)
const llmTesting = ref(false)
const embeddingTesting = ref(false)
const config = ref({
  base_url: '',
  api_key: '',
  model_name: '',
  timeout_s: 60,
  max_tokens: 4096,
})
const embeddingConfig = ref({
  base_url: '',
  api_key: '',
  model_name: '',
})

async function loadUsers() {
  loading.value = true
  const res = await client.get('/admin/users')
  users.value = res.data || []
  loading.value = false
}

async function loadConfig() {
  const res = await client.get('/admin/llm-config')
  if (!res.data.configured) {
    llmStatus.value = '未配置'
    return
  }
  llmStatus.value = '已配置'
  config.value = { ...config.value, ...res.data.config }
}

async function loadTokenUsage() {
  try {
    const res = await client.get('/admin/token-usage')
    totalTokens.value = res.data?.overall?.total_tokens || 0
    llmPromptTokens.value = res.data?.llm?.prompt_tokens || 0
    llmCompletionTokens.value = res.data?.llm?.completion_tokens || 0
    embeddingTokens.value = res.data?.embedding?.total_tokens || 0
  } catch {
    totalTokens.value = 0
    llmPromptTokens.value = 0
    llmCompletionTokens.value = 0
    embeddingTokens.value = 0
  }
}

async function saveConfig() {
  llmSaving.value = true
  try {
    await client.put('/admin/llm-config', config.value)
    llmStatus.value = '已更新'
  } finally {
    llmSaving.value = false
  }
}

async function loadEmbeddingConfig() {
  try {
    const res = await client.get('/admin/embedding-config')
    if (!res.data.configured) {
      embeddingStatus.value = '未配置 (使用哈希伪向量)'
      return
    }
    embeddingStatus.value = '已配置'
    embeddingConfig.value = { ...embeddingConfig.value, ...res.data.config }
  } catch {
    embeddingStatus.value = '加载失败'
  }
}

async function saveEmbeddingConfig() {
  embeddingSaving.value = true
  try {
    await client.put('/admin/embedding-config', embeddingConfig.value)
    embeddingStatus.value = '已更新'
  } finally {
    embeddingSaving.value = false
  }
}

async function testLlmConfig() {
  llmTesting.value = true
  llmTestStatus.value = ''
  try {
    const res = await client.post('/admin/llm-config/test')
    const { latency_ms, reply_preview } = res.data || {}
    llmTestStatus.value = `连接成功，耗时 ${latency_ms}ms，响应: ${reply_preview || 'OK'}`
  } catch (err: any) {
    llmTestStatus.value = `连接失败：${err?.response?.data?.detail || err?.message || '未知错误'}`
  } finally {
    llmTesting.value = false
  }
}

async function testEmbeddingConfig() {
  embeddingTesting.value = true
  embeddingTestStatus.value = ''
  try {
    const res = await client.post('/admin/embedding-config/test')
    const { latency_ms, dim } = res.data || {}
    embeddingTestStatus.value = `连接成功，耗时 ${latency_ms}ms，向量维度 ${dim}`
  } catch (err: any) {
    embeddingTestStatus.value = `连接失败：${err?.response?.data?.detail || err?.message || '未知错误'}`
  } finally {
    embeddingTesting.value = false
  }
}

async function updateUser(user: any) {
  await client.put(`/admin/users/${user.id}`, {
    role: user.role,
    is_active: user.is_active,
  })
}

async function removeUser(userId: string) {
  await client.delete(`/admin/users/${userId}`)
  users.value = users.value.filter(u => u.id !== userId)
}

onMounted(() => {
  loadUsers()
  loadConfig()
  loadEmbeddingConfig()
  loadTokenUsage()
})
</script>
