import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient, tokenStorage } from '@/api'
import {
  ApiError,
  type AuthTokensResponse,
  type UserLoginRequest,
  type UserProfileResponse,
  type UserRegisterRequest,
} from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const isInitialized = ref(false)
  const isSubmitting = ref(false)

  let initPromise: Promise<void> | null = null
  let sessionEpoch = 0
  let authActionSeq = 0

  const user = computed<UserProfileResponse | null>(() => tokenStorage.session.value?.user ?? null)

  const isAuthenticated = computed(() =>
    Boolean(tokenStorage.session.value?.accessToken && tokenStorage.session.value?.user),
  )

  const displayName = computed(() => {
    const trimmedName = user.value?.name?.trim()
    if (trimmedName) return trimmedName
    return user.value?.email ?? ''
  })

  const initials = computed(() => {
    const source = displayName.value.trim()
    if (!source) return 'YZ'
    const parts = source.split(/\s+/).filter(Boolean)
    if (parts.length >= 2) {
      return `${parts[0]?.[0] ?? ''}${parts[1]?.[0] ?? ''}`.toUpperCase()
    }
    return source.slice(0, 2).toUpperCase()
  })

  function applyAuthTokens(response: AuthTokensResponse): UserProfileResponse {
    sessionEpoch += 1
    tokenStorage.resetSession()
    tokenStorage.setFromAuthResponse(response, { isNewSession: true })
    isInitialized.value = true
    return response.user
  }

  function clearSession(options: { broadcastLogout?: boolean } = {}): void {
    sessionEpoch += 1
    tokenStorage.resetSession(options)
  }

  async function initialize(): Promise<void> {
    if (isInitialized.value) return
    if (initPromise) return initPromise

    initPromise = (async () => {
      const epochAtStart = sessionEpoch
      const genAtStart = tokenStorage.getSessionGen()

      try {
        if (!tokenStorage.getAccessToken()) {
          const refreshed = await apiClient.auth.refresh()
          if (sessionEpoch !== epochAtStart || tokenStorage.getSessionGen() !== genAtStart) {
            return
          }
          tokenStorage.setFromAuthResponse(refreshed)
        }

        const profile = await apiClient.auth.me()
        if (sessionEpoch !== epochAtStart || tokenStorage.getSessionGen() !== genAtStart) {
          return
        }

        tokenStorage.setUser(profile)
      } catch (error: unknown) {
        if (sessionEpoch === epochAtStart && tokenStorage.getSessionGen() === genAtStart) {
          const status = error instanceof ApiError ? error.status : 0
          if (status === 401 || status === 403) {
            clearSession()
          }
        }
      } finally {
        isInitialized.value = true
        initPromise = null
      }
    })()

    return initPromise
  }

  async function login(payload: UserLoginRequest): Promise<UserProfileResponse> {
    if (isSubmitting.value) {
      throw new ApiError({
        type: 'about:blank',
        title: 'Запрос уже выполняется',
        status: 409,
        detail: 'Дождитесь завершения текущей авторизации.',
      })
    }

    const actionSeq = ++authActionSeq
    isSubmitting.value = true
    try {
      const response = await apiClient.auth.login(payload)
      if (actionSeq !== authActionSeq) {
        return response.user
      }
      return applyAuthTokens(response)
    } finally {
      isSubmitting.value = false
    }
  }

  async function register(payload: UserRegisterRequest): Promise<UserProfileResponse> {
    if (isSubmitting.value) {
      throw new ApiError({
        type: 'about:blank',
        title: 'Запрос уже выполняется',
        status: 409,
        detail: 'Дождитесь завершения текущей регистрации.',
      })
    }

    const actionSeq = ++authActionSeq
    isSubmitting.value = true
    try {
      const response = await apiClient.auth.register(payload)
      if (actionSeq !== authActionSeq) {
        return response.user
      }
      return applyAuthTokens(response)
    } finally {
      isSubmitting.value = false
    }
  }

  async function logout(): Promise<void> {
    authActionSeq += 1
    clearSession({ broadcastLogout: true })
    isInitialized.value = true
    try {
      await apiClient.auth.logout()
    } catch {
      // Local state is already cleared; ignore transient network failure during logout.
    }
  }

  return {
    user,
    isInitialized,
    isSubmitting,
    isAuthenticated,
    displayName,
    initials,
    initialize,
    login,
    register,
    logout,
  }
})
