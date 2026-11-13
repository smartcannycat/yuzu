import type { HttpRequestFn } from '@/api/http/transport'
import type { AuthApi } from '@/api/types'
import type {
  AuthTokensResponse,
  TokenLogoutRequest,
  TokenRefreshRequest,
  UserLoginRequest,
  UserProfileResponse,
  UserRegisterRequest,
} from '@/types/api'

export function createHttpAuthApi(request: HttpRequestFn): AuthApi {
  return {
    register(payload: UserRegisterRequest): Promise<AuthTokensResponse> {
      return request<AuthTokensResponse>('/auth/register', {
        method: 'POST',
        body: payload,
        skipAuth: true,
        skipRefresh: true,
      })
    },

    login(payload: UserLoginRequest): Promise<AuthTokensResponse> {
      return request<AuthTokensResponse>('/auth/login', {
        method: 'POST',
        body: payload,
        skipAuth: true,
        skipRefresh: true,
      })
    },

    refresh(payload: TokenRefreshRequest): Promise<AuthTokensResponse> {
      return request<AuthTokensResponse>('/auth/refresh', {
        method: 'POST',
        body: payload,
        skipAuth: true,
        skipRefresh: true,
      })
    },

    logout(payload: TokenLogoutRequest): Promise<void> {
      return request<void>('/auth/logout', {
        method: 'POST',
        body: payload,
        skipRefresh: true,
      })
    },

    me(): Promise<UserProfileResponse> {
      return request<UserProfileResponse>('/auth/me', {
        method: 'GET',
      })
    },
  }
}
