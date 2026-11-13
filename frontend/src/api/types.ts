import type {
  AuthTokensResponse,
  TokenRefreshRequest,
  UserLoginRequest,
  UserProfileResponse,
  UserRegisterRequest,
} from '@/types/api'

export interface AuthApi {
  register(payload: UserRegisterRequest): Promise<AuthTokensResponse>
  login(payload: UserLoginRequest): Promise<AuthTokensResponse>
  refresh(payload: TokenRefreshRequest): Promise<AuthTokensResponse>
  me(): Promise<UserProfileResponse>
}

export interface ApiClient {
  auth: AuthApi
}
