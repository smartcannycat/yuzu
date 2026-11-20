import type {
  AuthTokensResponse,
  BatchCreateResponse,
  BatchProgressResponse,
  LotBulkDeleteRequest,
  LotBulkDeleteResponse,
  LotDetailResponse,
  LotLifecyclePatchRequest,
  LotListQueryParams,
  LotListResponse,
  LotSummary,
  RecalculateRequest,
  RecalculateResponse,
  UserLoginRequest,
  UserProfileResponse,
  UserRegisterRequest,
} from '@/types/api'

export interface RequestCancelOptions {
  signal?: AbortSignal
}

export interface AuthApi {
  register(payload: UserRegisterRequest): Promise<AuthTokensResponse>
  login(payload: UserLoginRequest): Promise<AuthTokensResponse>
  refresh(): Promise<AuthTokensResponse>
  logout(): Promise<void>
  me(): Promise<UserProfileResponse>
}

export interface LotsApi {
  list(params?: LotListQueryParams, options?: RequestCancelOptions): Promise<LotListResponse>
  getDetail(lotId: string, options?: RequestCancelOptions): Promise<LotDetailResponse>
  recalculate(lotId: string, payload: RecalculateRequest): Promise<RecalculateResponse>
  resetSimulation(lotId: string): Promise<RecalculateResponse>
  updateLifecycle(lotId: string, payload: LotLifecyclePatchRequest): Promise<LotSummary>
  deleteLot(lotId: string): Promise<void>
  bulkDeleteLots(payload: LotBulkDeleteRequest): Promise<LotBulkDeleteResponse>
  createBatch(files: readonly File[]): Promise<BatchCreateResponse>
  getBatch(batchId: string): Promise<BatchProgressResponse>
  appendBatchItems(batchId: string, files: readonly File[]): Promise<BatchProgressResponse>
}

export interface MediaApi {
  fetchBlob(url: string, options?: RequestCancelOptions): Promise<Blob>
}

export interface ApiClient {
  auth: AuthApi
  lots: LotsApi
  media: MediaApi
}
