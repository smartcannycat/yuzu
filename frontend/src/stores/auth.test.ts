import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient, tokenStorage } from '@/api'
import { DEMO_ACCOUNT_CREDENTIALS, resetMockUsers } from '@/api/mockApiClient'
import { AUTH_SYNC_STORAGE_KEY } from '@/api/tokenStorage'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/types/api'

describe('useAuthStore', () => {
  beforeEach(() => {
    tokenStorage.clear()
    resetMockUsers()
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('initializes unauthenticated when no cookie session exists and keeps zero tokens in localStorage', async () => {
    const store = useAuthStore()
    await store.initialize()

    expect(store.isInitialized).toBe(true)
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(window.localStorage.getItem('yuzu.auth.session')).toBeNull()
    expect(window.localStorage.getItem('yuzu.mock.session_user_id')).toBeNull()
    expect(window.localStorage.getItem(AUTH_SYNC_STORAGE_KEY)).toBeNull()
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i)
      const val = key ? (window.localStorage.getItem(key) ?? '') : ''
      expect(val).not.toContain('mock-access:')
      expect(val).not.toContain('access_token')
      expect(val).not.toContain('refresh_token')
    }
  })

  it('logs in in-memory only, restores session silently via refresh() -> me(), and calls logout()', async () => {
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
    // Ensure no access/refresh tokens are stored in localStorage.
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i)
      expect(key).not.toBe('yuzu.auth.session')
      const val = key ? (window.localStorage.getItem(key) ?? '') : ''
      expect(val).not.toContain('mock-access:')
    }

    // Simulate full page reload: clear in-memory tokenStorage & create fresh Pinia.
    tokenStorage.clear()
    setActivePinia(createPinia())
    const refreshSpy = vi.spyOn(apiClient.auth, 'refresh')
    const meSpy = vi.spyOn(apiClient.auth, 'me')
    const logoutSpy = vi.spyOn(apiClient.auth, 'logout')

    const reloadedStore = useAuthStore()
    await reloadedStore.initialize()
    expect(refreshSpy).toHaveBeenCalledTimes(1)
    expect(meSpy).toHaveBeenCalledTimes(1)
    expect(reloadedStore.isAuthenticated).toBe(true)
    expect(reloadedStore.user?.email).toBe(DEMO_ACCOUNT_CREDENTIALS.email)

    await reloadedStore.logout()
    expect(logoutSpy).toHaveBeenCalledTimes(1)
    expect(reloadedStore.isAuthenticated).toBe(false)
    expect(tokenStorage.getSession()).toBeNull()
  })

  it('clears local session synchronously on logout() while revoking server cookie', async () => {
    const store = useAuthStore()
    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(store.isAuthenticated).toBe(true)

    const logoutPromise = store.logout()

    expect(tokenStorage.getSession()).toBeNull()
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    await logoutPromise
  })

  it('does NOT clear in-memory session when initialize() encounters 5xx or network error (FE-MAJ-01)', async () => {
    const store = useAuthStore()
    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })

    const accessBefore = tokenStorage.getAccessToken()
    vi.spyOn(apiClient.auth, 'me').mockRejectedValueOnce(
      new ApiError({
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 503,
        detail: 'Temporary outage',
      }),
    )

    // Re-initialize a fresh Pinia store with existing in-memory token.
    setActivePinia(createPinia())
    const nextStore = useAuthStore()
    await nextStore.initialize()

    expect(nextStore.isInitialized).toBe(true)
    expect(nextStore.isAuthenticated).toBe(true)
    expect(tokenStorage.getAccessToken()).toBe(accessBefore)
  })

  it('registers a new account and clears stale invalid tokens on 401 initialize()', async () => {
    const store = useAuthStore()
    const created = await store.register({
      email: 'fresh@example.com',
      password: 'password123',
      name: 'Иван Петров',
    })

    expect(created.email).toBe('fresh@example.com')
    expect(store.initials).toBe('ИП')

    // Inject invalid access token and verify 401 on initialize() clears session cleanly.
    tokenStorage.setFromAuthResponse({
      access_token: 'invalid-token',
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

  it('guards login() and register() against concurrent submissions', async () => {
    let resolveLogin!: (val: Awaited<ReturnType<typeof apiClient.auth.login>>) => void
    const loginSpy = vi.spyOn(apiClient.auth, 'login').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve
        }),
    )

    const store = useAuthStore()
    const first = store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(store.isSubmitting).toBe(true)

    await expect(
      store.login({
        email: DEMO_ACCOUNT_CREDENTIALS.email,
        password: DEMO_ACCOUNT_CREDENTIALS.password,
      }),
    ).rejects.toMatchObject({ status: 409 })
    await expect(
      store.register({
        email: 'other@example.com',
        password: 'password123',
      }),
    ).rejects.toMatchObject({ status: 409 })
    expect(loginSpy).toHaveBeenCalledTimes(1)

    resolveLogin({
      access_token: 'mock-access:11111111-2222-4333-8444-555555555555:1',
      token_type: 'bearer',
      expires_in_sec: 3600,
      user: {
        user_id: '11111111-2222-4333-8444-555555555555',
        email: DEMO_ACCOUNT_CREDENTIALS.email,
        name: DEMO_ACCOUNT_CREDENTIALS.name,
        created_at: '2026-11-13T08:00:00Z',
      },
    })
    await first
    expect(store.isSubmitting).toBe(false)
    expect(store.isAuthenticated).toBe(true)
  })

  it('syncs cross-tab logout and account switch via BroadcastChannel / token-free StorageEvent', async () => {
    const store = useAuthStore()
    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(store.isAuthenticated).toBe(true)

    // Cross-tab logout ping (from another tab)
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: AUTH_SYNC_STORAGE_KEY,
        newValue: JSON.stringify({
          type: 'logout',
          senderId: 'other-tab-1',
          timestamp: Date.now(),
        }),
        storageArea: window.localStorage,
      }),
    )

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()

    // Re-login and simulate cross-tab switch to a different user
    await store.login({
      email: DEMO_ACCOUNT_CREDENTIALS.email,
      password: DEMO_ACCOUNT_CREDENTIALS.password,
    })
    expect(store.isAuthenticated).toBe(true)

    window.dispatchEvent(
      new StorageEvent('storage', {
        key: AUTH_SYNC_STORAGE_KEY,
        newValue: JSON.stringify({
          type: 'account-switch',
          senderId: 'other-tab-2',
          userId: '99999999-8888-4777-8666-555555555555',
          timestamp: Date.now(),
        }),
        storageArea: window.localStorage,
      }),
    )

    expect(store.isAuthenticated).toBe(false)
  })

  it('does not let stale initialize() failure wipe a newer login() session', async () => {
    tokenStorage.setFromAuthResponse({
      access_token: 'stale-access',
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
