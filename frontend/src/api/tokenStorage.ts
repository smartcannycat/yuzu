import type { AuthTokensResponse, UserProfileResponse } from '@/types/api'

const SESSION_STORAGE_KEY = 'yuzu.auth.session'

export interface StoredSession {
  accessToken: string
  refreshToken: string
  user: UserProfileResponse
}

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isValidUserProfile(value: unknown): value is UserProfileResponse {
  if (!isPlainRecord(value)) return false
  return (
    typeof value.user_id === 'string' &&
    value.user_id.length > 0 &&
    typeof value.email === 'string' &&
    value.email.length > 0 &&
    (value.name === null || typeof value.name === 'string') &&
    typeof value.created_at === 'string'
  )
}

export const tokenStorage = {
  getSession(): StoredSession | null {
    if (!canUseStorage()) return null
    try {
      const raw = window.localStorage.getItem(SESSION_STORAGE_KEY)
      if (!raw) return null
      const parsed: unknown = JSON.parse(raw)
      if (!isPlainRecord(parsed)) return null

      const { accessToken, refreshToken, user } = parsed
      if (
        typeof accessToken === 'string' &&
        accessToken.length > 0 &&
        typeof refreshToken === 'string' &&
        refreshToken.length > 0 &&
        isValidUserProfile(user)
      ) {
        return {
          accessToken,
          refreshToken,
          user,
        }
      }
      return null
    } catch {
      return null
    }
  },

  getAccessToken(): string | null {
    return this.getSession()?.accessToken ?? null
  },

  getRefreshToken(): string | null {
    return this.getSession()?.refreshToken ?? null
  },

  getUser(): UserProfileResponse | null {
    return this.getSession()?.user ?? null
  },

  setFromAuthResponse(response: AuthTokensResponse): void {
    if (!canUseStorage()) return
    const session: StoredSession = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      user: response.user,
    }
    try {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
    } catch {
      // Ignore storage quota errors in restricted browser contexts.
    }
  },

  setUser(user: UserProfileResponse): void {
    const current = this.getSession()
    if (!current || !canUseStorage()) return
    try {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ ...current, user }))
    } catch {
      // Ignore storage quota errors in restricted browser contexts.
    }
  },

  clear(): void {
    if (!canUseStorage()) return
    try {
      window.localStorage.removeItem(SESSION_STORAGE_KEY)
    } catch {
      // Ignore storage errors.
    }
  },
}
