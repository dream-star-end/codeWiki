<template>
  <div class="min-h-screen paper-texture flex items-center justify-center px-4">
    <div class="card-japanese w-full max-w-md p-6">
      <h1 class="text-xl font-bold text-[var(--accent-primary)] mb-2">用户登录</h1>
      <p class="text-sm text-[var(--muted)] mb-6">登录后可创建项目与查看我的项目</p>

      <div v-if="error" class="mb-4 p-3 rounded-lg bg-[var(--highlight)]/10 border border-[var(--highlight)]/30 text-[var(--highlight)] text-sm">
        {{ error }}
      </div>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">用户名或邮箱</label>
          <input v-model="username" class="input-japanese w-full" placeholder="请输入用户名或邮箱" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--foreground)] mb-2">密码</label>
          <input v-model="password" type="password" class="input-japanese w-full" placeholder="请输入密码" />
        </div>
        <button type="submit" class="btn-japanese w-full py-3" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <div class="mt-4 text-sm text-[var(--muted)]">
        还没有账号？
        <router-link to="/register" class="text-[var(--accent-primary)] hover:underline">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')

const loading = computed(() => auth.loading)
const error = computed(() => auth.error)

async function handleLogin() {
  const ok = await auth.login(username.value.trim(), password.value)
  if (ok) {
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  }
}
</script>
