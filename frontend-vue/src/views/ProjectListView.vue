<template>
  <div class="min-h-screen paper-texture">
    <!-- Header -->
    <header class="sticky top-0 z-10 bg-[var(--card-bg)] border-b border-[var(--border-color)] shadow-custom">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="bg-[var(--accent-primary)] p-2 rounded-lg">
            <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0014.07 6H17V4h-7V2H8v2H1v1.99h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/>
            </svg>
          </div>
          <div>
            <h1 class="text-xl font-bold text-[var(--accent-primary)]">CodeWiki</h1>
            <p class="text-xs text-[var(--muted)]">代码文档智能生成</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <router-link v-if="isLoggedIn" to="/my" class="text-sm text-[var(--foreground)] hover:text-[var(--accent-primary)]">我的项目</router-link>
          <router-link v-if="isLoggedIn" to="/password" class="text-sm text-[var(--foreground)] hover:text-[var(--accent-primary)]">修改密码</router-link>
          <router-link v-if="isAdmin" to="/admin" class="text-sm text-[var(--foreground)] hover:text-[var(--accent-primary)]">管理员后台</router-link>
          <router-link v-if="!isLoggedIn" to="/login" class="text-sm text-[var(--foreground)] hover:text-[var(--accent-primary)]">登录</router-link>
          <router-link v-if="!isLoggedIn" to="/register" class="text-sm text-[var(--foreground)] hover:text-[var(--accent-primary)]">注册</router-link>
          <button v-if="isLoggedIn" class="text-sm text-[var(--foreground)] hover:text-[var(--highlight)]" @click="logout">退出</button>
          <router-link v-if="isLoggedIn" to="/new" class="btn-japanese text-sm">+ 新建项目</router-link>
        </div>
      </div>
    </header>

    <!-- Hero Section -->
    <div class="bg-gradient-to-r from-[var(--accent-primary)] to-[var(--highlight)] text-white py-8">
      <div class="max-w-6xl mx-auto px-4 text-center">
        <p class="text-sm opacity-90 mb-4">浏览已生成的开源项目文档</p>
        <!-- Stats -->
        <div class="flex justify-center gap-12 mt-6">
          <div>
            <p class="text-3xl font-bold">{{ completedCount }}</p>
            <p class="text-xs opacity-80">已完成</p>
          </div>
          <div>
            <p class="text-3xl font-bold">{{ runningCount }}</p>
            <p class="text-xs opacity-80">生成中</p>
          </div>
          <div>
            <p class="text-3xl font-bold">{{ totalSymbols.toLocaleString() }}</p>
            <p class="text-xs opacity-80">符号数</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <main class="max-w-6xl mx-auto px-4 py-8">
      <!-- Search & Filter -->
      <div class="mb-6 flex flex-col sm:flex-row gap-4">
        <div class="relative flex-1">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="按名称或语言搜索项目..."
            class="input-japanese w-full pl-10 pr-4"
          />
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </div>
        <div class="flex gap-2 flex-wrap">
          <button
            v-for="lang in availableLanguages"
            :key="lang"
            @click="toggleLanguageFilter(lang)"
            :class="[
              'px-3 py-1.5 rounded-full text-sm border transition-colors',
              selectedLanguages.includes(lang)
                ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]'
                : 'bg-transparent text-[var(--foreground)] border-[var(--border-color)] hover:border-[var(--accent-primary)]'
            ]"
          >
            {{ lang }}
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading.repos" class="text-center py-12">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-primary)]"></div>
        <p class="mt-4 text-[var(--muted)]">加载项目列表...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-12">
        <p class="text-[var(--highlight)]">{{ error }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="filteredRepos.length === 0" class="text-center py-12">
        <p class="text-[var(--muted)]">暂无项目</p>
        <router-link to="/new" class="btn-japanese mt-4 inline-block">创建第一个项目</router-link>
      </div>

      <!-- Project Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="repo in filteredRepos"
          :key="repo.id"
          class="card-japanese p-5 hover:scale-[1.02] transition-transform relative"
          :class="{ 'opacity-80': isGenerating(repo) }"
        >
          <!-- Status Badge -->
          <div class="absolute top-3 right-3">
            <span v-if="isGenerating(repo)" 
                  class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-amber-100 text-amber-700 border border-amber-200">
              <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
              生成中
            </span>
            <span v-else-if="repo.job_status === 'failed'"
                  class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-red-100 text-red-700 border border-red-200">
              <span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>
              失败
            </span>
            <span v-else-if="repo.job_status === 'canceled'"
                  class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-600 border border-gray-200">
              <span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
              已取消
            </span>
            <span v-else-if="repo.job_status === 'success' || repo.modules > 0"
                  class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-100 text-green-700 border border-green-200">
              <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
              已完成
            </span>
          </div>

          <!-- Clickable area -->
          <div @click="handleCardClick(repo)" class="cursor-pointer">
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                   :class="repo.repo_type === 'local' ? 'bg-[var(--highlight)]/10' : 'bg-[var(--accent-primary)]/10'">
                <!-- GitHub Icon -->
                <svg v-if="repo.repo_type === 'github'" class="w-5 h-5 text-[var(--accent-primary)]" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                <!-- GitLab Icon -->
                <svg v-else-if="repo.repo_type === 'gitlab'" class="w-5 h-5 text-[var(--accent-primary)]" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 0 1-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 0 1 4.82 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.49h8.1l2.44-7.51A.42.42 0 0 1 18.6 2a.43.43 0 0 1 .58 0 .42.42 0 0 1 .11.18l2.44 7.51L23 13.45a.84.84 0 0 1-.35.94z"/>
                </svg>
                <!-- Local Folder Icon -->
                <svg v-else-if="repo.repo_type === 'local'" class="w-5 h-5 text-[var(--highlight)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
                </svg>
                <!-- Default Icon -->
                <svg v-else class="w-5 h-5 text-[var(--accent-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
                </svg>
              </div>
              <div class="flex-1 min-w-0 pr-16">
                <h3 class="font-semibold text-[var(--foreground)] line-clamp-1" :title="getDisplayName(repo)">
                  {{ getDisplayName(repo) }}
                </h3>
                <p class="text-xs text-[var(--muted)] mt-0.5">{{ repo.repo_type === 'local' ? '本地项目' : repo.owner }}</p>
              </div>
            </div>
            
            <!-- Progress bar for generating repos -->
            <div v-if="isGenerating(repo)" class="mt-4">
              <div class="flex items-center justify-between text-xs text-[var(--muted)] mb-1">
                <span>{{ repo.job_stage || '处理中' }}</span>
                <span>{{ repo.job_progress }}%</span>
              </div>
              <div class="w-full bg-[var(--border-color)] rounded-full h-1.5 overflow-hidden">
                <div
                  class="bg-gradient-to-r from-[var(--accent-primary)] to-[var(--highlight)] h-1.5 rounded-full transition-all duration-500"
                  :style="{ width: `${repo.job_progress}%` }"
                ></div>
              </div>
              <p class="text-xs text-[var(--muted)] mt-1">{{ repo.job_detail }}</p>
            </div>

            <!-- Language Tags (only for completed) -->
            <div v-else class="flex flex-wrap gap-1.5 mt-3">
              <span
                v-for="lang in (repo.languages || []).slice(0, 3)"
                :key="lang"
                class="px-2 py-0.5 text-xs rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20"
              >
                {{ lang }}
              </span>
              <span v-if="(repo.languages || []).length > 3" class="px-2 py-0.5 text-xs rounded-full bg-[var(--background)] text-[var(--muted)]">
                +{{ repo.languages.length - 3 }}
              </span>
            </div>

            <!-- Stats (only for completed) -->
            <div v-if="!isGenerating(repo)" class="flex items-center gap-4 mt-4 pt-3 border-t border-[var(--border-color)]">
              <div class="text-center">
                <p class="text-sm font-semibold text-[var(--accent-primary)]">{{ repo.symbols }}</p>
                <p class="text-xs text-[var(--muted)]">符号</p>
              </div>
              <div class="text-center">
                <p class="text-sm font-semibold text-[var(--accent-primary)]">{{ repo.depth }}</p>
                <p class="text-xs text-[var(--muted)]">深度</p>
              </div>
              <div class="text-center">
                <p class="text-sm font-semibold text-[var(--accent-primary)]">{{ repo.modules }}</p>
                <p class="text-xs text-[var(--muted)]">模块</p>
              </div>
              <div class="text-center">
                <p class="text-sm font-semibold text-[var(--accent-primary)]">{{ (repo.token_usage || 0).toLocaleString() }}</p>
                <p class="text-xs text-[var(--muted)]">Wiki Tokens</p>
              </div>
            </div>
          </div>

          <!-- Actions (only for completed) -->
          <div v-if="!isGenerating(repo)" class="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--border-color)]">
            <a
              v-if="getGitUrl(repo)"
              :href="getGitUrl(repo)"
              target="_blank"
              @click.stop
              class="text-xs text-[var(--link-color)] hover:text-[var(--accent-primary)] flex items-center gap-1"
            >
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
              源码仓库
            </a>
            <router-link
              :to="`/wiki/${repo.id}`"
              class="text-xs text-[var(--link-color)] hover:text-[var(--accent-primary)] flex items-center gap-1"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
              查看文档
            </router-link>
            <button
              v-if="repo.job_status !== 'running' && repo.job_status !== 'queued'"
              class="text-xs text-[var(--accent-primary)] hover:underline"
              @click.stop="updateProject(repo.id)"
            >
              更新文档
            </button>
            <button
              v-if="repo.job_status === 'failed'"
              class="text-xs text-[var(--accent-primary)] hover:underline"
              @click.stop="retryJob(repo.id)"
            >
              断点重试
            </button>
            <button
              v-if="isAdmin"
              class="text-xs text-[var(--highlight)] hover:underline"
              @click.stop="deleteProject(repo.id)"
            >
              删除
            </button>
          </div>
          <div v-else class="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--border-color)]">
            <button
              class="text-xs text-[var(--accent-primary)] hover:underline"
              @click.stop="cancelJob(repo.id)"
            >
              取消任务
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- Progress Modal -->
    <div v-if="showProgressModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click="showProgressModal = false">
      <div class="bg-[var(--card-bg)] rounded-xl p-6 max-w-md w-full mx-4 shadow-xl" @click.stop>
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-[var(--foreground)]">生成进度</h3>
          <button @click="showProgressModal = false" class="text-[var(--muted)] hover:text-[var(--foreground)]">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        
        <div v-if="selectedRepo" class="space-y-4">
          <div class="text-sm text-[var(--foreground)]">
            <strong>{{ getDisplayName(selectedRepo) }}</strong>
          </div>
          
          <!-- Stage Header -->
          <div class="flex items-center gap-3">
            <div class="relative">
              <div class="animate-spin rounded-full h-6 w-6 border-2 border-[var(--accent-primary)]/30 border-t-[var(--accent-primary)]"></div>
            </div>
            <div class="flex-1">
              <h4 class="text-sm font-semibold text-[var(--foreground)]">{{ selectedRepo.job_stage || '准备中' }}</h4>
              <p class="text-xs text-[var(--muted)] mt-0.5">{{ selectedRepo.job_detail || '正在初始化...' }}</p>
            </div>
            <span class="text-lg font-bold text-[var(--accent-primary)]">{{ selectedRepo.job_progress }}%</span>
          </div>
          
          <!-- Progress Bar -->
          <div class="w-full bg-[var(--border-color)] rounded-full h-2.5 overflow-hidden">
            <div
              class="bg-gradient-to-r from-[var(--accent-primary)] to-[var(--highlight)] h-2.5 rounded-full transition-all duration-500 ease-out"
              :style="{ width: `${selectedRepo.job_progress}%` }"
            ></div>
          </div>

          <!-- Progress Steps -->
          <div class="grid grid-cols-5 gap-1 text-center text-xs">
            <div :class="selectedRepo.job_progress >= 15 ? 'text-[var(--accent-primary)]' : 'text-[var(--muted)]'">
              <div class="w-2 h-2 rounded-full mx-auto mb-1" :class="selectedRepo.job_progress >= 15 ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-color)]'"></div>
              克隆
            </div>
            <div :class="selectedRepo.job_progress >= 40 ? 'text-[var(--accent-primary)]' : 'text-[var(--muted)]'">
              <div class="w-2 h-2 rounded-full mx-auto mb-1" :class="selectedRepo.job_progress >= 40 ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-color)]'"></div>
              解析
            </div>
            <div :class="selectedRepo.job_progress >= 75 ? 'text-[var(--accent-primary)]' : 'text-[var(--muted)]'">
              <div class="w-2 h-2 rounded-full mx-auto mb-1" :class="selectedRepo.job_progress >= 75 ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-color)]'"></div>
              文档
            </div>
            <div :class="selectedRepo.job_progress >= 90 ? 'text-[var(--accent-primary)]' : 'text-[var(--muted)]'">
              <div class="w-2 h-2 rounded-full mx-auto mb-1" :class="selectedRepo.job_progress >= 90 ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-color)]'"></div>
              索引
            </div>
            <div :class="selectedRepo.job_progress >= 100 ? 'text-[var(--accent-primary)]' : 'text-[var(--muted)]'">
              <div class="w-2 h-2 rounded-full mx-auto mb-1" :class="selectedRepo.job_progress >= 100 ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-color)]'"></div>
              完成
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <footer class="border-t border-[var(--border-color)] bg-[var(--card-bg)] py-6">
      <div class="max-w-6xl mx-auto px-4 text-center text-sm text-[var(--muted)]">
        CodeWiki · 代码文档智能生成
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWikiStore } from '../stores/wiki'
import { useAuthStore } from '../stores/auth'
import { apiClient } from '../services/api'
import { storeToRefs } from 'pinia'

const router = useRouter()
const store = useWikiStore()
const auth = useAuthStore()
const client = apiClient(auth.apiBase)
const { repos, loading, error } = storeToRefs(store)

const searchQuery = ref('')
const selectedLanguages = ref<string[]>([])
const showProgressModal = ref(false)
const selectedRepo = ref<any>(null)

const isLoggedIn = computed(() => auth.isLoggedIn)
const isAdmin = computed(() => auth.isAdmin)

let refreshInterval: number | null = null

onMounted(() => {
  store.loadRepos()
  // Auto-refresh progress only (lightweight, no full reload)
  refreshInterval = window.setInterval(async () => {
    if (hasGeneratingProjects.value) {
      // Use lightweight progress update instead of full reload
      const refreshNeeded = await store.updateReposProgress()
      // Update selected repo if modal is open
      if (showProgressModal.value && selectedRepo.value) {
        const updated = repos.value.find(r => r.id === selectedRepo.value.id)
        if (updated) {
          selectedRepo.value = updated
          // Auto-close modal if completed
          if (!isGenerating(updated)) {
            showProgressModal.value = false
            // Reload full list once when a job completes to get updated stats
            store.loadRepos()
          }
        }
      }
      if (refreshNeeded) {
        store.loadRepos()
      }
    }
  }, 2000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

function isGenerating(repo: any): boolean {
  return repo.job_status === 'running' || repo.job_status === 'queued'
}

const hasGeneratingProjects = computed(() => repos.value.some(r => isGenerating(r)))

const completedCount = computed(() => repos.value.filter(r => r.job_status === 'success' || r.modules > 0).length)
const runningCount = computed(() => repos.value.filter(r => isGenerating(r)).length)

const availableLanguages = computed(() => {
  const langSet = new Set<string>()
  repos.value.forEach(r => (r.languages || []).forEach((l: string) => langSet.add(l)))
  return Array.from(langSet).slice(0, 7)
})

const filteredRepos = computed(() => {
  let result = repos.value
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(r =>
      (r.name || '').toLowerCase().includes(q) ||
      (r.repo || '').toLowerCase().includes(q) ||
      (r.owner || '').toLowerCase().includes(q) ||
      (r.languages || []).some((l: string) => l.toLowerCase().includes(q))
    )
  }
  if (selectedLanguages.value.length > 0) {
    result = result.filter(r =>
      selectedLanguages.value.some(lang => (r.languages || []).includes(lang))
    )
  }
  return result
})

const totalSymbols = computed(() => repos.value.reduce((sum, r) => sum + (r.symbols || 0), 0))

function toggleLanguageFilter(lang: string) {
  const idx = selectedLanguages.value.indexOf(lang)
  if (idx >= 0) {
    selectedLanguages.value.splice(idx, 1)
  } else {
    selectedLanguages.value.push(lang)
  }
}

function handleCardClick(repo: any) {
  if (isGenerating(repo)) {
    selectedRepo.value = repo
    showProgressModal.value = true
  } else {
    router.push(`/wiki/${repo.id}`)
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}

async function deleteProject(repoId: string) {
  if (!confirm('确定要删除该项目吗？删除后无法恢复。')) return
  await client.delete(`/repos/${repoId}`)
  await store.loadRepos()
}

async function cancelJob(repoId: string) {
  if (!confirm('确定要取消该任务吗？')) return
  await client.post(`/repos/${repoId}/cancel`)
  await store.loadRepos()
}

async function retryJob(repoId: string) {
  if (!confirm('确定要从断点继续生成该项目吗？')) return
  await client.post(`/repos/${repoId}/retry`)
  await store.loadRepos()
}

async function updateProject(repoId: string) {
  if (!confirm('确定要检查代码更新并更新文档吗？')) return
  await client.post(`/repos/${repoId}/update`)
  await store.loadRepos()
}

function getDisplayName(repo: any): string {
  // For GitHub/GitLab repos, show owner/repo
  if (repo.repo_type === 'github' || repo.repo_type === 'gitlab' || repo.repo_type === 'bitbucket') {
    if (repo.owner && repo.repo) {
      return `${repo.owner}/${repo.repo}`
    }
  }
  // For local repos, show just the folder name
  if (repo.repo_type === 'local' && repo.source) {
    const parts = repo.source.replace(/\\/g, '/').split('/')
    return parts[parts.length - 1] || repo.repo || repo.name
  }
  return repo.name || repo.repo || repo.id
}

function getGitUrl(repo: any): string {
  if (repo.repo_type === 'local') {
    return '' // Local repos don't have a git URL
  }
  if (repo.source && repo.source.startsWith('http')) {
    return repo.source
  }
  if (repo.repo_type === 'github' && repo.owner && repo.repo) {
    return `https://github.com/${repo.owner}/${repo.repo}`
  }
  if (repo.repo_type === 'gitlab' && repo.owner && repo.repo) {
    return `https://gitlab.com/${repo.owner}/${repo.repo}`
  }
  if (repo.repo_type === 'bitbucket' && repo.owner && repo.repo) {
    return `https://bitbucket.org/${repo.owner}/${repo.repo}`
  }
  return ''
}
</script>
