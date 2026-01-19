import axios from 'axios'

export type ModelConfig = {
  base_url: string
  api_key: string
  model_name: string
  max_tokens: number
  timeout_s: number
}

export type IngestPayload = {
  url?: string | null
  local_path?: string | null
  include?: string[] | null
  exclude?: string[] | null
  model?: ModelConfig | null
}

export const apiClient = (baseURL: string) => {
  const client = axios.create({ baseURL })
  client.interceptors.request.use(config => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
  return client
}
