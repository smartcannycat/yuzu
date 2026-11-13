import { useStorage, type Serializer } from '@vueuse/core'

import type { AuthTokensResponse, UserProfileResponse } from '@/types/api'

export const SESSION_STORAGE_KEY = 'yuzu.auth.session'

export interface StoredSession {
  accessToken: string
  refreshToken: string
  user: UserProfileResponse
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

function parseSessionObject(parsed: unknown): StoredSession | null {
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
}

const sessionSerializer: Serializer<StoredSession | null> = {
  read(raw: string): StoredSession | null {
    try {
      return parseSessionObject(JSON.parse(raw))
    } catch {
      return null
    }
  },
  write(value: StoredSession | null): string {
    return JSON.stringify(value)
  },
}

const session = useStorage<StoredSession | null>(SESSION_STORAGE_KEY, null, undefined, {
  flush: 'sync',
  writeDefaults: false,
  serializer: sessionSerializer,
  onError: () => {
    // Ignore storage quota errors in restricted browser contexts.
  },
})

export const tokenStorage = {
  session,

  getSession(): StoredSession | null {
    return session.value
  },

  getAccessToken(): string | null {
    return session.value?.accessToken ?? null
  },

  getRefreshToken(): string | null {
    return session.value?.refreshToken ?? null
  },

  getUser(): UserProfileResponse | null {
    return session.value?.user ?? null
  },

  setFromAuthResponse(response: AuthTokensResponse): void {
    session.value = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      user: response.user,
    }
  },

  setUser(user: UserProfileResponse): void {
    if (!session.value) return
    session.value = {
      ...session.value,
      user,
    }
  },

  clear(): void {
    session.value = null
  },
}
