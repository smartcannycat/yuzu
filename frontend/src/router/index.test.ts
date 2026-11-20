import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { tokenStorage } from '@/api'
import { DEMO_ACCOUNT_CREDENTIALS, resetMockUsers } from '@/api/mockApiClient'
import { useAuthStore } from '@/stores/auth'

describe('router guards and routes', () => {
  beforeEach(() => {
    tokenStorage.clear()
    resetMockUsers()
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
    vi.restoreAllMocks()
  })

  it('redirects unauthenticated users to /auth preserving redirect and preserves ?redirect= on /login and /register', async () => {
    const { createAppRouter } = await import('@/router')
    const router = createAppRouter(createMemoryHistory())

    await router.push('/lots/abc?tab=tech')
    expect(router.currentRoute.value.name).toBe('auth')
    expect(router.currentRoute.value.query.redirect).toBe('/lots/abc?tab=tech')

    await router.push('/login?redirect=/lots/abc')
    expect(router.currentRoute.value.name).toBe('auth')
    expect(router.currentRoute.value.query.mode).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/lots/abc')

    await router.push('/register?redirect=/lots/abc')
    expect(router.currentRoute.value.name).toBe('auth')
    expect(router.currentRoute.value.query.mode).toBe('register')
    expect(router.currentRoute.value.query.redirect).toBe('/lots/abc')
  })

  it('redirects authenticated users away from guestOnly routes safely and rejects unsafe redirect targets', async () => {
    const { createAppRouter } = await import('@/router')
    const router = createAppRouter(createMemoryHistory())
    const authStore = useAuthStore()

    await authStore.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })

    await router.push('/auth?redirect=/lots/42')
    expect(router.currentRoute.value.fullPath).toBe('/lots/42')

    await router.push('/auth?redirect=/\\evil.com')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('handles 404 fallback route and omits /ui-kit when import.meta.env.DEV is false', async () => {
    const { createAppRouter } = await import('@/router')
    const devRouter = createAppRouter(createMemoryHistory())
    expect(devRouter.hasRoute('ui-kit')).toBe(true)
    expect(devRouter.hasRoute('not-found')).toBe(true)

    const authStore = useAuthStore()
    await authStore.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })

    await devRouter.push('/non-existent/page')
    expect(devRouter.currentRoute.value.name).toBe('home')

    // Verify production mode omits /ui-kit route
    vi.resetModules()
    const origDev = import.meta.env.DEV
    import.meta.env.DEV = false
    try {
      const { createAppRouter: createProdRouter } = await import('@/router')
      const prodRouter = createProdRouter(createMemoryHistory())
      expect(prodRouter.hasRoute('ui-kit')).toBe(false)
      expect(prodRouter.resolve('/ui-kit').name).toBe('not-found')
    } finally {
      import.meta.env.DEV = origDev
    }
  })
})
