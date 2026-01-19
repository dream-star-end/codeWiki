import type { RouteRecordRaw } from 'vue-router'
import ProjectListView from '../views/ProjectListView.vue'
import WikiDetailView from '../views/WikiDetailView.vue'
import NewProjectView from '../views/NewProjectView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import AdminView from '../views/AdminView.vue'
import MyProjectsView from '../views/MyProjectsView.vue'
import ResetPasswordView from '../views/ResetPasswordView.vue'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'projects', component: ProjectListView, meta: { requiresAuth: true } },
  { path: '/projects', redirect: '/' },
  { path: '/new', name: 'new', component: NewProjectView, meta: { requiresAuth: true } },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/register', name: 'register', component: RegisterView },
  { path: '/my', name: 'my-projects', component: MyProjectsView, meta: { requiresAuth: true } },
  { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/password', name: 'password', component: ResetPasswordView, meta: { requiresAuth: true } },
  { path: '/wiki/:id', name: 'wiki', component: WikiDetailView },
]
