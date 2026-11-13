import type {
  AuthTokensResponse,
  BatchCreateResponse,
  BatchProgressResponse,
  LotListQueryParams,
  LotListResponse,
  TokenLogoutRequest,
  TokenRefreshRequest,
  UserLoginRequest,
  UserProfileResponse,
  UserRegisterRequest,
} from '@/types/api'

export interface AuthApi {
  register(payload: UserRegisterRequest): Promise<AuthTokensResponse>
  login(payload: UserLoginRequest): Promise<AuthTokensResponse>
  refresh(payload: TokenRefreshRequest): Promise<AuthTokensResponse>
  logout(payload: TokenLogoutRequest): Promise<void>
  me(): Promise<UserProfileResponse>
}

export interface LotsApi {
  list(params?: LotListQueryParams): Promise<LotListResponse>
  createBatch(files: readonly File[]): Promise<BatchCreateResponse>
  getBatch(batchId: string): Promise<BatchProgressResponse>
  appendBatchItems(batchId: string, files: readonly File[]): Promise<BatchProgressResponse>
}

export interface ApiClient {
  auth: AuthApi
  lots: LotsApi
}
