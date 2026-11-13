import { useStorage, type Serializer } from '@vueuse/core'

import { createMockProblem, delay, generateUuid } from '@/api/mock/helpers'
import { tokenStorage } from '@/api/tokenStorage'
import type { AuthApi } from '@/api/types'
import type {
  AuthTokensResponse,
  InvalidParamDetail,
  TokenLogoutRequest,
  TokenRefreshRequest,
  UserLoginRequest,
  UserProfileResponse,
  UserRegisterRequest,
} from '@/types/api'
import {
  isValidEmailFormat,
  NAME_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
} from '@/utils/validation'

export const MOCK_USERS_STORAGE_KEY = 'yuzu.mock.users'
const ACCESS_TOKEN_PREFIX = 'mock-access:'
const REFRESH_TOKEN_PREFIX = 'mock-refresh:'

export const DEMO_ACCOUNT_CREDENTIALS = {
  email: 'alex@example.com',
  password: 'password123',
  name: 'Алексей',
} as const

interface MockUserRecord extends UserProfileResponse {
  password: string
}

const DEFAULT_DEMO_USER: MockUserRecord = {
  user_id: '11111111-2222-4333-8444-555555555555',
  email: DEMO_ACCOUNT_CREDENTIALS.email,
  password: DEMO_ACCOUNT_CREDENTIALS.password,
  name: DEMO_ACCOUNT_CREDENTIALS.name,
  created_at: '2026-11-13T08:00:00Z',
}

let mockUnauthorizedHandler: (() => void) | null = null

export function setMockUnauthorizedHandler(handler: (() => void) | null): void {
  mockUnauthorizedHandler = handler
}

function isValidMockUser(value: unknown): value is MockUserRecord {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const record = value as Record<string, unknown>
  return (
    typeof record.user_id === 'string' &&
    record.user_id.length > 0 &&
    typeof record.email === 'string' &&
    record.email.length > 0 &&
    typeof record.password === 'string' &&
    (record.name === null || typeof record.name === 'string') &&
    typeof record.created_at === 'string'
  )
}

const mockUsersSerializer: Serializer<MockUserRecord[]> = {
  read(raw: string): MockUserRecord[] {
    try {
      const parsed: unknown = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        const validUsers = parsed.filter(isValidMockUser)
        if (validUsers.length > 0) {
          return validUsers
        }
      }
    } catch {
      // Fallback to seeded demo user if storage payload is corrupted.
    }
    return [DEFAULT_DEMO_USER]
  },
  write(value: MockUserRecord[]): string {
    return JSON.stringify(value)
  },
}

const mockUsersStorage = useStorage<MockUserRecord[]>(
  MOCK_USERS_STORAGE_KEY,
  () => [DEFAULT_DEMO_USER],
  undefined,
  {
    flush: 'sync',
    writeDefaults: false,
    serializer: mockUsersSerializer,
    onError: () => {
      // Ignore storage quota errors.
    },
  },
)

const revokedRefreshTokens = new Set<string>()

export function resetMockUsers(): void {
  mockUsersStorage.value = [DEFAULT_DEMO_USER]
  revokedRefreshTokens.clear()
}

function toPublicProfile(record: MockUserRecord): UserProfileResponse {
  return {
    user_id: record.user_id,
    email: record.email,
    name: record.name,
    created_at: record.created_at,
  }
}

function createTokensResponse(record: MockUserRecord): AuthTokensResponse {
  const profile = toPublicProfile(record)
  const nonce = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
  return {
    access_token: `${ACCESS_TOKEN_PREFIX}${record.user_id}:${nonce}`,
    refresh_token: `${REFRESH_TOKEN_PREFIX}${record.user_id}:${nonce}`,
    token_type: 'bearer',
    expires_in_sec: 3600,
    user: profile,
  }
}

function extractUserIdFromToken(token: string, prefix: string): string | null {
  if (!token.startsWith(prefix)) return null
  const body = token.slice(prefix.length)
  const [userId] = body.split(':')
  return userId || null
}

export function createMockAuthApi(defaultDelay: number): AuthApi {
  return {
    async register(payload: UserRegisterRequest): Promise<AuthTokensResponse> {
      await delay(defaultDelay)
      const email = payload.email.trim().toLowerCase()
      const password = payload.password
      const name = payload.name?.trim() || null

      const invalidParams: InvalidParamDetail[] = []
      if (!isValidEmailFormat(email)) {
        invalidParams.push({
          name: 'email',
          reason: 'Укажите корректный адрес электронной почты',
        })
      }
      if (password.length < PASSWORD_MIN_LENGTH || password.length > PASSWORD_MAX_LENGTH) {
        invalidParams.push({
          name: 'password',
          reason: `Пароль должен содержать от ${PASSWORD_MIN_LENGTH} до ${PASSWORD_MAX_LENGTH} символов`,
        })
      }
      if (name && name.length > NAME_MAX_LENGTH) {
        invalidParams.push({
          name: 'name',
          reason: `Имя не должно превышать ${NAME_MAX_LENGTH} символов`,
        })
      }

      if (invalidParams.length > 0) {
        throw createMockProblem({
          slug: 'validation-error',
          title: 'Ошибка валидации параметров',
          status: 422,
          detail: invalidParams[0]?.reason ?? 'Проверьте корректность заполнения полей',
          instance: '/api/v1/auth/register',
          invalidParams,
        })
      }

      const users = mockUsersStorage.value
      const exists = users.some((user) => user.email.toLowerCase() === email)
      if (exists) {
        throw createMockProblem({
          slug: 'email-conflict',
          title: 'Email уже зарегистрирован',
          status: 409,
          detail: `Аккаунт с адресом ${email} уже существует. Выполните вход или используйте другой email.`,
          instance: '/api/v1/auth/register',
          invalidParams: [
            {
              name: 'email',
              reason: 'Этот email уже зарегистрирован',
            },
          ],
        })
      }

      const newUser: MockUserRecord = {
        user_id: generateUuid(),
        email,
        password,
        name,
        created_at: new Date().toISOString(),
      }
      mockUsersStorage.value = [...users, newUser]
      return createTokensResponse(newUser)
    },

    async login(payload: UserLoginRequest): Promise<AuthTokensResponse> {
      await delay(defaultDelay)
      const email = payload.email.trim().toLowerCase()
      const users = mockUsersStorage.value
      const matched = users.find(
        (user) => user.email.toLowerCase() === email && user.password === payload.password,
      )

      if (!matched) {
        throw createMockProblem({
          slug: 'invalid-credentials',
          title: 'Неверный email или пароль',
          status: 401,
          detail: 'Проверьте правильность введенного email и пароля.',
          instance: '/api/v1/auth/login',
        })
      }

      return createTokensResponse(matched)
    },

    async refresh(payload: TokenRefreshRequest): Promise<AuthTokensResponse> {
      await delay(Math.min(defaultDelay, 120))
      const userId = extractUserIdFromToken(payload.refresh_token, REFRESH_TOKEN_PREFIX)
      const users = mockUsersStorage.value
      const matched =
        userId && !revokedRefreshTokens.has(payload.refresh_token)
          ? users.find((user) => user.user_id === userId)
          : undefined

      if (!matched) {
        throw createMockProblem({
          slug: 'invalid-token',
          title: 'Сессия истекла',
          status: 401,
          detail: 'Refresh-токен недействителен или истек. Войдите в аккаунт повторно.',
          instance: '/api/v1/auth/refresh',
        })
      }

      return createTokensResponse(matched)
    },

    async logout(payload: TokenLogoutRequest): Promise<void> {
      await delay(Math.min(defaultDelay, 80))
      if (payload.refresh_token) {
        revokedRefreshTokens.add(payload.refresh_token)
      }
    },

    async me(): Promise<UserProfileResponse> {
      await delay(Math.min(defaultDelay, 120))
      const accessToken = tokenStorage.getAccessToken()
      const users = mockUsersStorage.value
      const userId = accessToken ? extractUserIdFromToken(accessToken, ACCESS_TOKEN_PREFIX) : null
      const matched = userId ? users.find((user) => user.user_id === userId) : undefined

      if (matched) {
        return toPublicProfile(matched)
      }

      const refreshToken = tokenStorage.getRefreshToken()
      if (refreshToken) {
        try {
          const refreshed = await this.refresh({ refresh_token: refreshToken })
          tokenStorage.setFromAuthResponse(refreshed)
          return refreshed.user
        } catch {
          // Fall through to 401 cleanup.
        }
      }

      tokenStorage.clear()
      mockUnauthorizedHandler?.()
      throw createMockProblem({
        slug: 'unauthorized',
        title: 'Требуется авторизация',
        status: 401,
        detail: 'Сессия не найдена или истекла.',
        instance: '/api/v1/auth/me',
      })
    },
  }
}
