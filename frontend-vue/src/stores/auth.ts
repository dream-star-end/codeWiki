import { defineStore } from 'pinia'
import { apiClient } from '../services/api'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export type UserInfo = {
  id: string
  username: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at?: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    apiBase: localStorage.getItem('api_base') || DEFAULT_API_BASE,
    token: localStorage.getItem('auth_token') || '',
    user: null as UserInfo | null,
    loading: false,
    error: '',
  }),
  getters: {
    isLoggedIn: state => !!state.token,
    isAdmin: state => state.user?.role === 'admin',
  },
  actions: {
    setError(err: unknown, fallback: string) {
      const anyErr = err as any
      const apiDetail = anyErr?.response?.data?.detail
      if (typeof apiDetail === 'string' && apiDetail.trim()) {
        this.error = apiDetail
        return
      }
      if (Array.isArray(apiDetail) && apiDetail.length > 0) {
        // FastAPI validation errors (422)
        const msg = apiDetail
          .map((item: any) => item?.msg || item?.message)
          .filter(Boolean)
          .join('；')
        if (msg) {
          this.error = msg
          return
        }
      }
      if (err instanceof Error && err.message) {
        this.error = err.message
      } else if (typeof err === 'string') {
        this.error = err
      } else {
        this.error = fallback
      }
    },
    clearError() {
      this.error = ''
    },
    async register(username: string, email: string, password: string) {
      this.clearError()
      this.loading = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.post('/auth/register', { username, email, password })
        this.token = res.data.access_token
        this.user = res.data.user
        localStorage.setItem('auth_token', this.token)
        return true
      } catch (err) {
        this.setError(err, '注册失败')
        return false
      } finally {
        this.loading = false
      }
    },
    async login(username: string, password: string) {
      this.clearError()
      this.loading = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.post('/auth/login', { username, password })
        this.token = res.data.access_token
        this.user = res.data.user
        localStorage.setItem('auth_token', this.token)
        return true
      } catch (err) {
        this.setError(err, '登录失败')
        return false
      } finally {
        this.loading = false
      }
    },
    async loadMe() {
      if (!this.token) return
      this.clearError()
      this.loading = true
      try {
        const client = apiClient(this.apiBase)
        const res = await client.get('/auth/me')
        this.user = res.data
      } catch (err) {
        this.setError(err, '获取用户信息失败')
      } finally {
        this.loading = false
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('auth_token')
    },
  },
})
