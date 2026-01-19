<template>
  <div class="min-h-screen paper-texture">
    <!-- Header -->
    <header class="sticky top-0 z-10 bg-[var(--card-bg)] border-b border-[var(--border-color)] shadow-custom">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <router-link to="/" class="text-[var(--accent-primary)] hover:text-[var(--highlight)] flex items-center gap-1 text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
            </svg>
            返回列表
          </router-link>
        </div>
        <div class="flex items-center gap-2">
          <div class="bg-[var(--accent-primary)] p-1.5 rounded">
            <svg class="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0014.07 6H17V4h-7V2H8v2H1v1.99h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/>
            </svg>
          </div>
          <h1 class="text-lg font-bold text-[var(--accent-primary)]">新建项目</h1>
        </div>
      </div>
    </header>

    <main class="max-w-2xl mx-auto px-4 py-8">
      <div class="card-japanese p-6">
        <h2 class="text-xl font-semibold text-[var(--foreground)] mb-6">生成代码文档</h2>
        
        <!-- Error Alert -->
        <div v-if="error" class="mb-4 p-3 rounded-lg bg-[var(--highlight)]/10 border border-[var(--highlight)]/30 text-[var(--highlight)] text-sm">
          {{ error }}
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-5">
          <!-- Repository URL -->
          <div>
            <label class="block text-sm font-medium text-[var(--foreground)] mb-2">Git 仓库地址</label>
            <input
              v-model="repoUrl"
              type="text"
              placeholder="https://github.com/user/repo 或本地路径"
              class="input-japanese w-full"
              :disabled="isSubmitting"
            />
            <p class="text-xs text-[var(--muted)] mt-1">支持 GitHub、GitLab、Bitbucket 或本地文件夹路径</p>
          </div>

          <!-- Include/Exclude Patterns -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-[var(--foreground)] mb-2">包含规则</label>
              <input
                v-model="include"
                type="text"
                placeholder="*.py,src/**"
                class="input-japanese w-full"
                :disabled="isSubmitting"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-[var(--foreground)] mb-2">排除规则</label>
              <input
                v-model="exclude"
                type="text"
                placeholder="test/**,*.test.js"
                class="input-japanese w-full"
                :disabled="isSubmitting"
              />
            </div>
          </div>

          <!-- Submit Button -->
          <div class="pt-4">
            <button
              type="submit"
              :disabled="isSubmitting || !repoUrl.trim()"
              class="btn-japanese w-full py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ isSubmitting ? '生成中...' : '开始生成 Wiki' }}
            </button>
          </div>
        </form>

        <!-- Submitting -->
        <div v-if="isSubmitting" class="mt-6 p-4 rounded-lg bg-[var(--background)] border border-[var(--border-color)]">
          <div class="flex items-center gap-3">
            <div class="animate-spin rounded-full h-5 w-5 border-2 border-[var(--accent-primary)]/30 border-t-[var(--accent-primary)]"></div>
            <span class="text-sm text-[var(--foreground)]">正在提交任务，稍后将跳转到项目列表...</span>
          </div>
        </div>
      </div>

      <!-- Tips -->
      <div class="mt-6 p-4 rounded-lg bg-[var(--accent-primary)]/5 border border-[var(--accent-primary)]/20">
        <h3 class="text-sm font-semibold text-[var(--accent-primary)] mb-2">使用提示</h3>
        <ul class="text-xs text-[var(--muted)] space-y-1">
          <li>• AI 模型配置通过环境变量设置：VITE_LLM_BASE_URL, VITE_LLM_API_KEY, VITE_LLM_MODEL</li>
          <li>• 大型仓库建议使用排除规则过滤测试和文档文件夹</li>
          <li>• 生成过程可能需要几分钟，请耐心等待</li>
        </ul>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWikiStore } from '../stores/wiki'

const router = useRouter()
const store = useWikiStore()

const repoUrl = ref('')
const include = ref('')
const exclude = ref('')
const isSubmitting = ref(false)
const error = ref('')


async function handleSubmit() {
  if (!repoUrl.value.trim()) return
  
  error.value = ''
  isSubmitting.value = true
  
  try {
    // Submit the ingest job
    await store.ingest({
      url: repoUrl.value.startsWith('/') || repoUrl.value.match(/^[a-zA-Z]:/) ? null : repoUrl.value,
      local_path: repoUrl.value.startsWith('/') || repoUrl.value.match(/^[a-zA-Z]:/) ? repoUrl.value : null,
      include: include.value ? include.value.split(',').map(s => s.trim()) : null,
      exclude: exclude.value ? exclude.value.split(',').map(s => s.trim()) : null,
      model: store.model,
    })

    // Redirect to project list immediately - the job runs in background
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '提交失败'
    isSubmitting.value = false
  }
}
</script>
