<template>
  <div class="min-h-screen paper-texture flex items-center justify-center px-4">
    <div class="card-japanese w-full max-w-md p-6">
      <h1 class="text-xl font-bold text-[var(--accent-primary)] mb-2">修改密码</h1>
      <p class="text-sm text-[var(--muted)] mb-6">请先输入当前密码</p>

      <div v-if="message" class="mb-4 p-3 rounded-lg bg-[var(--accent-primary)]/10 border border-[var(--accent-primary)]/30 text-[var(--accent-primary)] text-sm">
        {{ message }}
      </div>
      <div v-if="error" class="mb-4 p-3 rounded-lg bg-[var(--highlight)]/10 border border-[var(--highlight)]/30 text-[var(--highlight)] text-sm">
        {{ error }}
      </div>

      <form @submit.prevent="handleReset" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">当前密码</label>
          <input v-model="oldPassword" type="password" class="input-japanese w-full" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">新密码</label>
          <input v-model="newPassword" type="password" class="input-japanese w-full" />
        </div>
        <button type="submit" class="btn-japanese w-full py-3" :disabled="loading">
          {{ loading ? '提交中...' : '更新密码' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { apiClient } from '../services/api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const client = apiClient(auth.apiBase)

const oldPassword = ref('')
const newPassword = ref('')
const loading = ref(false)
const message = ref('')
const error = ref('')

async function handleReset() {
  loading.value = true
  message.value = ''
  error.value = ''
  try {
    await client.post('/auth/password/reset', {
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    message.value = '密码已更新'
    oldPassword.value = ''
    newPassword.value = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '更新失败'
  } finally {
    loading.value = false
  }
}
</script>
