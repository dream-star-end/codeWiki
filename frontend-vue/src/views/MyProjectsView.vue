<template>
  <div class="min-h-screen paper-texture">
    <header class="sticky top-0 z-10 bg-[var(--card-bg)] border-b border-[var(--border-color)] shadow-custom">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <router-link to="/" class="text-[var(--accent-primary)] hover:text-[var(--highlight)] flex items-center gap-1 text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
            </svg>
            返回项目列表
          </router-link>
          <h1 class="text-lg font-bold text-[var(--accent-primary)]">我的项目</h1>
        </div>
        <router-link to="/new" class="btn-japanese text-sm">+ 新建项目</router-link>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8">
      <div v-if="loading.myRepos" class="text-center py-12">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-primary)]"></div>
        <p class="mt-4 text-[var(--muted)]">加载中...</p>
      </div>

      <div v-else-if="error" class="text-center py-12">
        <p class="text-[var(--highlight)]">{{ error }}</p>
      </div>

      <div v-else-if="myRepos.length === 0" class="text-center py-12">
        <p class="text-[var(--muted)]">还没有项目</p>
        <router-link to="/new" class="btn-japanese mt-4 inline-block">创建第一个项目</router-link>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="repo in myRepos"
          :key="repo.id"
          class="card-japanese p-5 hover:scale-[1.02] transition-transform relative"
          :class="{ 'opacity-80': isGenerating(repo) }"
        >
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
            <span v-else
                  class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-100 text-green-700 border border-green-200">
              <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
              已完成
            </span>
          </div>

          <div @click="handleCardClick(repo)" class="cursor-pointer">
            <h3 class="font-semibold text-[var(--foreground)] line-clamp-1">{{ repo.name || repo.repo }}</h3>
            <p class="text-xs text-[var(--muted)] mt-1">{{ repo.repo_type }}</p>
            <p class="text-xs text-[var(--muted)] mt-1">Wiki Token 消耗：{{ (repo.token_usage || 0).toLocaleString() }}</p>
          </div>

          <div class="mt-3 pt-3 border-t border-[var(--border-color)] flex items-center justify-between">
            <button
              v-if="isGenerating(repo)"
              class="text-xs text-[var(--accent-primary)] hover:underline"
              @click.stop="cancelJob(repo.id)"
            >
              取消任务
            </button>
            <button
              v-else-if="repo.job_status === 'failed'"
              class="text-xs text-[var(--accent-primary)] hover:underline"
              @click.stop="retryJob(repo.id)"
            >
              断点重试
            </button>
            <button
              v-else
              class="text-xs text-[var(--accent-primary)] hover:underline"
              @click.stop="updateProject(repo.id)"
            >
              更新文档
            </button>
            <button
              class="text-xs text-[var(--highlight)] hover:underline"
              @click.stop="deleteProject(repo.id)"
            >
              删除项目
            </button>
            <router-link
              v-if="!isGenerating(repo)"
              :to="`/wiki/${repo.id}`"
              class="text-xs text-[var(--link-color)] hover:text-[var(--accent-primary)]"
            >
              查看文档
            </router-link>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiClient } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useWikiStore } from '../stores/wiki'
import { storeToRefs } from 'pinia'

const router = useRouter()
const auth = useAuthStore()
const store = useWikiStore()
const client = apiClient(auth.apiBase)
const { myRepos, loading, error } = storeToRefs(store)

let refreshInterval: number | null = null

onMounted(() => {
  store.loadMyRepos()
  // Auto-refresh progress only (lightweight, no full reload)
  refreshInterval = window.setInterval(async () => {
    if (hasGeneratingProjects.value) {
      const refreshNeeded = await store.updateReposProgress()
      if (refreshNeeded) {
        store.loadMyRepos()
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

const hasGeneratingProjects = computed(() => myRepos.value.some(r => isGenerating(r)))

function handleCardClick(repo: any) {
  if (isGenerating(repo)) return
  router.push(`/wiki/${repo.id}`)
}

async function deleteProject(repoId: string) {
  if (!confirm('确定要删除该项目吗？删除后无法恢复。')) return
  await client.delete(`/repos/${repoId}`)
  await store.loadMyRepos()
}

async function cancelJob(repoId: string) {
  if (!confirm('确定要取消该任务吗？')) return
  await client.post(`/repos/${repoId}/cancel`)
  await store.loadMyRepos()
}

async function retryJob(repoId: string) {
  if (!confirm('确定要从断点继续生成该项目吗？')) return
  await client.post(`/repos/${repoId}/retry`)
  await store.loadMyRepos()
}

async function updateProject(repoId: string) {
  if (!confirm('确定要检查代码更新并更新文档吗？')) return
  await client.post(`/repos/${repoId}/update`)
  await store.loadMyRepos()
}
</script>
