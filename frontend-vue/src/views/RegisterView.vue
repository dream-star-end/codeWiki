<template>
  <div class="min-h-screen paper-texture flex items-center justify-center px-4">
    <div class="card-japanese w-full max-w-md p-6">
      <h1 class="text-xl font-bold text-[var(--accent-primary)] mb-2">用户注册</h1>
      <p class="text-sm text-[var(--muted)] mb-6">创建账号以生成和管理项目</p>

      <div v-if="error" class="mb-4 p-3 rounded-lg bg-[var(--highlight)]/10 border border-[var(--highlight)]/30 text-[var(--highlight)] text-sm">
        {{ error }}
      </div>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">用户名</label>
          <input v-model="username" class="input-japanese w-full" placeholder="请输入用户名（至少 3 个字符）" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">邮箱</label>
          <input v-model="email" type="email" class="input-japanese w-full" placeholder="请输入邮箱（有效格式）" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">密码</label>
          <input v-model="password" type="password" class="input-japanese w-full" placeholder="请输入密码（至少 6 位）" />
        </div>
        <button type="submit" class="btn-japanese w-full py-3" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>

      <div class="mt-4 text-sm text-[var(--muted)]">
        已有账号？
        <router-link to="/login" class="text-[var(--accent-primary)] hover:underline">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const email = ref('')
const password = ref('')

const loading = computed(() => auth.loading)
const error = computed(() => auth.error)

async function handleRegister() {
  if (username.value.trim().length < 3) {
    auth.setError('用户名至少 3 个字符', '用户名至少 3 个字符')
    return
  }
  if (password.value.length < 6) {
    auth.setError('密码至少 6 位', '密码至少 6 位')
    return
  }
  const ok = await auth.register(username.value.trim(), email.value.trim(), password.value)
  if (ok) {
    router.push('/')
  }
}
</script>
