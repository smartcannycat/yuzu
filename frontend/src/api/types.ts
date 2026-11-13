import type {
  AuthTokensResponse,
  LotListQueryParams,
  LotListResponse,
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

export interface LotsApi {
  list(params?: LotListQueryParams): Promise<LotListResponse>
}

export interface ApiClient {
  auth: AuthApi
  lots: LotsApi
}
