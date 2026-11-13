import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient, DEMO_ACCOUNT_CREDENTIALS, tokenStorage } from '@/api'
import { resetMockUsers } from '@/api/mockApiClient'
import { SESSION_STORAGE_KEY } from '@/api/tokenStorage'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'

describe('useAuthStore', () => {
  beforeEach(() => {
    tokenStorage.clear()
    resetMockUsers()
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it('initializes unauthenticated when storage is empty', async () => {
    const store = useAuthStore()
    await store.initialize()

    expect(store.isInitialized).toBe(true)
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
  })

  it('logs in, persists tokens, restores session on initialize, and logs out', async () => {
    const store = useAuthStore()
    const profile = await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })

    expect(profile.email).toBe(DEMO_ACCOUNT_CREDENTIALS.email)
    expect(store.isAuthenticated).toBe(true)
    expect(store.displayName).toBe(DEMO_ACCOUNT_CREDENTIALS.name)
    expect(store.initials).toBe('АЛ')
    expect(tokenStorage.getAccessToken()).toBeTruthy()

    // Simulate fresh Pinia store hydration after page reload.
    setActivePinia(createPinia())
    const reloadedStore = useAuthStore()
    await reloadedStore.initialize()
    expect(reloadedStore.isAuthenticated).toBe(true)
    expect(reloadedStore.user?.email).toBe(DEMO_ACCOUNT_CREDENTIALS.email)

    await reloadedStore.logout()
    expect(reloadedStore.isAuthenticated).toBe(false)
    expect(tokenStorage.getSession()).toBeNull()
  })

  it('clears local session and storage synchronously on logout', async () => {
    const store = useAuthStore()
    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(tokenStorage.getRefreshToken()).toBeTruthy()
    expect(store.isAuthenticated).toBe(true)

    store.logout()

    expect(tokenStorage.getSession()).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
  })

  it('registers a new account and clears stale invalid tokens on initialize', async () => {
    const store = useAuthStore()
    const created = await store.register({
      email: 'fresh@example.com',
      password: 'password123',
      name: 'Иван Петров',
    })

    expect(created.email).toBe('fresh@example.com')
    expect(store.initials).toBe('ИП')

    // Inject invalid tokens and verify initialize clears session cleanly.
    tokenStorage.setFromAuthResponse({
      access_token: 'invalid-token',
      refresh_token: 'invalid-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: created,
    })

    setActivePinia(createPinia())
    const brokenStore = useAuthStore()
    await brokenStore.initialize()
    expect(brokenStore.isAuthenticated).toBe(false)
    expect(tokenStorage.getSession()).toBeNull()
  })

  it('syncs cross-tab logout via VueUse useStorage StorageEvent', async () => {
    const store = useAuthStore()
    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(store.isAuthenticated).toBe(true)

    window.dispatchEvent(
      new StorageEvent('storage', {
        key: SESSION_STORAGE_KEY,
        newValue: null,
        storageArea: window.localStorage,
      }),
    )

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
  })

  it('does not let stale initialize() failure wipe a newer login() session', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'stale-access',
      refresh_token: 'stale-refresh',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: {
        user_id: '00000000-0000-4000-8000-000000000000',
        email: 'stale@example.com',
        name: null,
        created_at: '2026-11-13T08:00:00Z',
      },
    })

    let rejectMe!: (err: unknown) => void
    const meSpy = vi.spyOn(apiClient.auth, 'me').mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectMe = reject
        }),
    )

    const store = useAuthStore()
    const initPromise = store.initialize()

    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })

    rejectMe(
      new ApiError({
        type: 'about:blank',
        title: 'Unauthorized',
        status: 401,
        detail: 'Expired',
      }),
    )
    await initPromise

    expect(store.isAuthenticated).toBe(true)
    expect(store.user?.email).toBe(DEMO_ACCOUNT_CREDENTIALS.email)
    expect(tokenStorage.getAccessToken()).toBeTruthy()
    meSpy.mockRestore()
  })
})
