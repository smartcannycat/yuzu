import {
  createRouter,
  createWebHistory,
  type Router,
  type RouterHistory,
  type RouteRecordRaw,
} from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { isSafeRelativePath } from '@/utils/url'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guestOnly?: boolean
  }
}

function buildAppRoutes(): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/lots/:lotId',
      name: 'lot-detail',
      component: () => import('@/views/LotDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/batches/:batchId',
      name: 'batch-progress',
      component: () => import('@/views/BatchProgressView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/auth',
      name: 'auth',
      component: () => import('@/views/AuthView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/login',
      name: 'login',
      redirect: (to) => ({
        name: 'auth',
        query: { ...to.query, mode: 'login' },
      }),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      redirect: (to) => ({
        name: 'auth',
        query: { ...to.query, mode: 'register' },
      }),
      meta: { guestOnly: true },
    },
  ]

  if (import.meta.env.DEV) {
    routes.push({
      path: '/ui-kit',
      name: 'ui-kit',
      component: () => import('@/views/UiKitView.vue'),
    })
  }

  routes.push({
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    redirect: '/',
  })

  return routes
}

function resolveAuthenticatedRedirectTarget(rawRedirect: unknown): string | { name: 'home' } {
  if (typeof rawRedirect === 'string') {
    const trimmed = rawRedirect.trim()
    if (
      isSafeRelativePath(trimmed) &&
      !trimmed.startsWith('/auth') &&
      !trimmed.startsWith('/login') &&
      !trimmed.startsWith('/register')
    ) {
      return trimmed
    }
  }
  return { name: 'home' }
}

export function createAppRouter(
  history: RouterHistory = createWebHistory(import.meta.env.BASE_URL),
): Router {
  const appRouter = createRouter({
    history,
    routes: buildAppRoutes(),
  })

  appRouter.beforeEach(async (to) => {
    const authStore = useAuthStore()
    await authStore.initialize()

    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
      return {
        name: 'auth',
        query: to.fullPath !== '/' ? { redirect: to.fullPath } : undefined,
      }
    }

    if (to.meta.guestOnly && authStore.isAuthenticated) {
      return resolveAuthenticatedRedirectTarget(to.query.redirect)
    }

    return true
  })

  return appRouter
}

export const router = createAppRouter()

export default router
