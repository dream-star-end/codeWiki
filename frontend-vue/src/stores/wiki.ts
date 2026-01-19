import { defineStore } from 'pinia'
import { apiClient, type IngestPayload, type ModelConfig } from '../services/api'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export type PageKind = 'overview' | 'module' | 'ai-module'

export type PageItem = {
  title: string
  content: string
  files: string[]
  moduleId?: string
  kind?: PageKind
}

export type RepoListItem = {
  id: string
  name: string
  owner: string
  repo: string
  repo_type: string
  source: string
  languages: string[]
  modules: number
  symbols: number
  files: number
  depth: number
  created_at: string
  job_id?: string
  job_status?: string
  job_progress?: number
  job_stage?: string
  job_detail?: string
  token_usage?: number
}

export type DepsPayload = {
  file_deps: any[]
  symbol_deps: any[]
  module_deps: any[]
}

const STORAGE_KEY = 'deepwiki_model_config_v1'

export const useWikiStore = defineStore('wiki', {
  state: () => ({
    apiBase: localStorage.getItem('api_base') || DEFAULT_API_BASE,
    repoId: '' as string,
    jobId: '' as string,
    status: 'Ready.' as string,
    jobProgress: 0 as number,
    jobStage: '' as string,
    jobDetail: '' as string,
    pages: [] as PageItem[],
    currentIndex: 0 as number,
    deps: { file_deps: [], symbol_deps: [], module_deps: [] } as DepsPayload,
    answer: '' as string,
    aiSummary: '' as string,
    aiModules: [] as { module_id: string; content: string }[],
    moduleDocs: {} as Record<string, string>,
    repos: [] as RepoListItem[],
    myRepos: [] as RepoListItem[],
    error: '' as string,
    loading: {
      ingest: false,
      poll: false,
      summary: false,
      deps: false,
      aiSummary: false,
      aiModules: false,
      answer: false,
      repos: false,
      myRepos: false,
      docs: {} as Record<string, boolean>,
    },
    model: loadModelConfig(),
  }),
  actions: {
    clearError() {
      this.error = ''
    },
    setError(err: unknown, fallback: string) {
      this.error = normalizeError(err, fallback)
    },
    setStatus(text: string) {
      this.status = text
    },
    setModel(model: ModelConfig) {
      this.model = model
      saveModelConfig(model, this.apiBase)
    },
    async ingest(payload: IngestPayload) {
      this.clearError()
      this.loading.ingest = true
      this.setStatus('Submitting...')
      try {
        const client = apiClient(this.apiBase)
        const res = await client.post('/repos/ingest', payload)
        this.repoId = res.data.repo_id
        this.jobId = res.data.job_id
        this.setStatus('Job submitted')
      } catch (err) {
        this.setStatus('failed')
        this.setError(err, 'Failed to submit ingest job.')
        throw err
      } finally {
        this.loading.ingest = false
      }
    },
    async pollJob() {
      if (!this.jobId) return
      this.clearError()
      this.loading.poll = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get(`/jobs/${this.jobId}`)
        const data = res.data
        this.jobProgress = data.progress || 0
        this.jobStage = data.stage || ''
        this.jobDetail = data.detail || ''
        this.setStatus(`${data.status} ${data.progress}% ${data.error || ''}`.trim())
        return data.status
      } catch (err) {
        this.setStatus('failed')
        this.setError(err, 'Failed to poll job status.')
        throw err
      } finally {
        this.loading.poll = false
      }
    },
    async loadSummary(language: 'zh' | 'en' = 'en') {
      if (!this.repoId) return
      this.clearError()
      this.loading.summary = true
      try {
        const client = apiClient(this.apiBase)
        const [summary, modules, overviewDoc] = await Promise.all([
          client.get(`/repos/${this.repoId}/summary`),
          client.get(`/repos/${this.repoId}/modules`),
          client.get(`/repos/${this.repoId}/docs/root`).catch(() => ({ data: { content: '' } })),
        ])
        this.pages = buildPages(
          summary.data,
          modules.data.modules || [],
          overviewDoc.data?.content || '',
          this.aiSummary,
          this.aiModules,
          language,
          this.moduleDocs,
        )
        this.currentIndex = 0
      } catch (err) {
        this.setError(err, 'Failed to load summary.')
        throw err
      } finally {
        this.loading.summary = false
      }
    },
    async loadRepos() {
      this.clearError()
      this.loading.repos = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get('/repos')
        this.repos = res.data.repos || []
      } catch (err) {
        this.setError(err, 'Failed to load repository list.')
        throw err
      } finally {
        this.loading.repos = false
      }
    },
    async loadMyRepos() {
      this.clearError()
      this.loading.myRepos = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get('/repos/my')
        this.myRepos = res.data.repos || []
      } catch (err) {
        this.setError(err, 'Failed to load my repository list.')
        throw err
      } finally {
        this.loading.myRepos = false
      }
    },
    async updateReposProgress(): Promise<boolean> {
      // Lightweight progress update - only fetch running repos progress
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get('/repos/progress')
        const progressList = res.data.repos || []
        let missingRunning = false
        
        // Create a map for quick lookup
        const progressMap = new Map<string, any>()
        progressList.forEach((p: any) => progressMap.set(p.id, p))
        
        // Update repos list in-place
        this.repos = this.repos.map(repo => {
          const progress = progressMap.get(repo.id)
          if (progress) {
            // Update progress fields only
            return {
              ...repo,
              job_status: progress.job_status,
              job_progress: progress.job_progress,
              job_stage: progress.job_stage,
              job_detail: progress.job_detail,
            }
          } else if (repo.job_status === 'running' || repo.job_status === 'queued') {
            // Job disappeared from progress list - trigger full refresh
            missingRunning = true
          }
          return repo
        })
        
        // Also update myRepos if it has data
        if (this.myRepos.length > 0) {
          this.myRepos = this.myRepos.map(repo => {
            const progress = progressMap.get(repo.id)
            if (progress) {
              return {
                ...repo,
                job_status: progress.job_status,
                job_progress: progress.job_progress,
                job_stage: progress.job_stage,
                job_detail: progress.job_detail,
              }
            } else if (repo.job_status === 'running' || repo.job_status === 'queued') {
              missingRunning = true
            }
            return repo
          })
        }
        return missingRunning
      } catch {
        // Silently fail - this is just a progress update
        return false
      }
    },
    async loadDeps() {
      if (!this.repoId) return
      this.clearError()
      this.loading.deps = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get(`/repos/${this.repoId}/deps`)
        this.deps = res.data
      } catch (err) {
        this.setError(err, 'Failed to load dependency graphs.')
        throw err
      } finally {
        this.loading.deps = false
      }
    },
    async ask(query: string) {
      if (!this.repoId) return
      this.clearError()
      this.loading.answer = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.post(`/repos/${this.repoId}/answer`, {
          query,
          model: this.model,
        })
        this.answer = res.data.answer
      } catch (err) {
        this.setError(err, 'Failed to generate an answer.')
        throw err
      } finally {
        this.loading.answer = false
      }
    },
    async loadAiSummary() {
      if (!this.repoId) return
      this.clearError()
      this.loading.aiSummary = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.post(`/repos/${this.repoId}/ai/summary`, {
          model: this.model,
        })
        this.aiSummary = res.data.content || ''
      } catch (err) {
        this.setError(err, 'Failed to load AI summary.')
        throw err
      } finally {
        this.loading.aiSummary = false
      }
    },
    async loadAiModules() {
      if (!this.repoId) return
      this.clearError()
      this.loading.aiModules = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.post(`/repos/${this.repoId}/ai/modules`, {
          model: this.model,
          max_modules: 12,
        })
        this.aiModules = res.data.modules || []
      } catch (err) {
        this.setError(err, 'Failed to load AI module docs.')
        throw err
      } finally {
        this.loading.aiModules = false
      }
    },
    async loadModuleDoc(moduleId?: string) {
      if (!this.repoId || !moduleId) return
      if (this.moduleDocs[moduleId]) return
      this.clearError()
      this.loading.docs[moduleId] = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get(`/repos/${this.repoId}/docs/${moduleId}`)
        const content = res.data.content || ''
        this.moduleDocs[moduleId] = content
        const page = this.pages.find((item) => item.moduleId === moduleId)
        if (page && content) {
          page.content = content
        }
      } catch (err) {
        this.setError(err, 'Failed to load module documentation.')
        throw err
      } finally {
        this.loading.docs[moduleId] = false
      }
    },
  },
})

function buildPages(
  summary: any,
  modules: any[],
  overviewDoc: string,
  aiSummary: string,
  aiModules: { module_id: string; content: string }[],
  language: 'zh' | 'en',
  moduleDocs: Record<string, string>,
): PageItem[] {
  const pages: PageItem[] = []
  const titleGettingStarted = language === 'zh' ? '概览' : 'Overview'
  const summaryPlaceholder =
    language === 'zh' ? 'AI 总览会在这里生成。' : 'AI summary will appear here.'
  const moduleLabel = language === 'zh' ? '模块' : 'Module'
  const pathLabel = language === 'zh' ? '路径' : 'Path'
  const moduleDocPlaceholder =
    language === 'zh' ? '选择模块以加载文档。' : 'Select a module to load documentation.'
  const summaryContent =
    overviewDoc || aiSummary || buildSummaryMarkdown(summary, language) || summaryPlaceholder
  pages.push({
    title: titleGettingStarted,
    content: summaryContent,
    files: [],
    kind: 'overview',
  })
  const filteredModules = modules.filter((mod) => {
    const moduleId = mod.module_id || mod.id || ''
    const pathPrefix = mod.path_prefix || ''
    return moduleId !== 'root' && pathPrefix !== ''
  })
  filteredModules.forEach((mod) => {
    const moduleId = mod.module_id || mod.id
    const cachedDoc = moduleId ? moduleDocs[moduleId] : ''
    const contentParts = [`${pathLabel}: ${mod.path_prefix || moduleId || moduleLabel}`]
    if (!cachedDoc) {
      contentParts.push('', moduleDocPlaceholder)
    }
    pages.push({
      title: mod.name || mod.path_prefix || moduleLabel,
      content: cachedDoc || contentParts.join('\n'),
      files: mod.files || [],
      moduleId,
      kind: 'module',
    })
  })
  aiModules.slice(0, 12).forEach((doc) => {
    pages.push({
      title: language === 'zh' ? `模块: ${doc.module_id}` : `Module: ${doc.module_id}`,
      content: doc.content || '',
      files: [],
      moduleId: doc.module_id,
      kind: 'ai-module',
    })
  })
  return pages
}

function buildSummaryMarkdown(summary: any, language: 'zh' | 'en') {
  if (!summary) return ''
  const lines: string[] = []
  const langTitle = language === 'zh' ? '语言' : 'Languages'
  const entryTitle = language === 'zh' ? '入口文件' : 'Entry Points'
  const languages = formatLanguages(summary.languages)
  if (languages.length) {
    lines.push(`## ${langTitle}`, ...languages.map((item) => `- ${item}`), '')
  }
  const entries = Array.isArray(summary.entry_points) ? summary.entry_points : []
  if (entries.length) {
    const entryLines = entries.map((item: any) => {
      if (typeof item === 'string') return item
      return item.file_path || item.name || JSON.stringify(item)
    })
    lines.push(`## ${entryTitle}`, ...entryLines.map((item: string) => `- ${item}`), '')
  }
  return lines.join('\n').trim()
}

function formatLanguages(languages: any): string[] {
  if (!languages) return []
  if (Array.isArray(languages)) return languages.map(String)
  if (typeof languages === 'object') {
    return Object.entries(languages).map(([name, count]) => `${name} (${count})`)
  }
  return []
}

function loadModelConfig(): ModelConfig {
  // Priority: Environment variables > localStorage
  const envBaseUrl = import.meta.env.VITE_LLM_BASE_URL || ''
  const envApiKey = import.meta.env.VITE_LLM_API_KEY || ''
  const envModel = import.meta.env.VITE_LLM_MODEL || ''
  
  // If environment variables are set, use them
  if (envBaseUrl || envApiKey || envModel) {
    return {
      base_url: envBaseUrl,
      api_key: envApiKey,
      model_name: envModel,
      max_tokens: 1024,
      timeout_s: 60,
    }
  }
  
  // Fallback to localStorage
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return {
      base_url: '',
      api_key: '',
      model_name: '',
      max_tokens: 1024,
      timeout_s: 60,
    }
  }
  try {
    const data = JSON.parse(raw)
    return {
      base_url: data.base_url || '',
      api_key: data.api_key || '',
      model_name: data.model_name || '',
      max_tokens: 1024,
      timeout_s: 60,
    }
  } catch {
    return {
      base_url: '',
      api_key: '',
      model_name: '',
      max_tokens: 1024,
      timeout_s: 60,
    }
  }
}

function saveModelConfig(model: ModelConfig, apiBase: string) {
  const data = {
    base_url: model.base_url,
    api_key: model.api_key,
    model_name: model.model_name,
    api_base: apiBase,
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  localStorage.setItem('api_base', apiBase)
}

function normalizeError(err: unknown, fallback: string) {
  if (err instanceof Error && err.message) return err.message
  if (typeof err === 'string') return err
  return fallback
}
