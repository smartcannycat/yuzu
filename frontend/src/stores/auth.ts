import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient, tokenStorage } from '@/api'
import { useLotsStore } from '@/stores/lots'
import type {
  AuthTokensResponse,
  UserLoginRequest,
  UserProfileResponse,
  UserRegisterRequest,
} from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const isInitialized = ref(false)
  const isSubmitting = ref(false)

  let initPromise: Promise<void> | null = null
  let sessionEpoch = 0

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
    tokenStorage.setFromAuthResponse(response)
    isInitialized.value = true
    return response.user
  }

  function clearSession(): void {
    sessionEpoch += 1
    tokenStorage.clear()
    useLotsStore().clear()
  }

  async function initialize(): Promise<void> {
    if (isInitialized.value) return
    if (initPromise) return initPromise

    initPromise = (async () => {
      const epochAtStart = sessionEpoch
      try {
        const hasToken = Boolean(tokenStorage.getAccessToken() || tokenStorage.getRefreshToken())
        if (!hasToken) {
          if (sessionEpoch === epochAtStart) {
            clearSession()
          }
          return
        }

        const profile = await apiClient.auth.me()
        if (sessionEpoch !== epochAtStart) return

        tokenStorage.setUser(profile)
      } catch {
        if (sessionEpoch === epochAtStart) {
          clearSession()
        }
      } finally {
        isInitialized.value = true
        initPromise = null
      }
    })()

    return initPromise
  }

  async function login(payload: UserLoginRequest): Promise<UserProfileResponse> {
    isSubmitting.value = true
    try {
      const response = await apiClient.auth.login(payload)
      return applyAuthTokens(response)
    } finally {
      isSubmitting.value = false
    }
  }

  async function register(payload: UserRegisterRequest): Promise<UserProfileResponse> {
    isSubmitting.value = true
    try {
      const response = await apiClient.auth.register(payload)
      return applyAuthTokens(response)
    } finally {
      isSubmitting.value = false
    }
  }

  function logout(): void {
    clearSession()
    isInitialized.value = true
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
