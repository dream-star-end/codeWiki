import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { routes } from './router'
import './style.css'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()
const router = createRouter({
  history: createWebHistory(),
  routes,
})

app.use(pinia)
app.use(router)
app.mount('#app')

// Auth guard
const auth = useAuthStore(pinia)
auth.loadMe()

router.beforeEach((to, _from, next) => {
  const requiresAuth = to.meta.requiresAuth
  const requiresAdmin = to.meta.requiresAdmin

  if (requiresAuth && !auth.isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  if (requiresAdmin && !auth.isAdmin) {
    next({ path: '/' })
    return
  }

  next()
})
