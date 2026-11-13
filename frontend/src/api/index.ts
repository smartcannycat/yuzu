import { createHttpApiClient, setHttpUnauthorizedHandler } from '@/api/httpClient'
import {
  createMockApiClient,
  DEMO_ACCOUNT_CREDENTIALS,
  setMockUnauthorizedHandler,
} from '@/api/mockApiClient'
import { tokenStorage } from '@/api/tokenStorage'
import type { ApiClient } from '@/api/types'

export const isMockMode = import.meta.env.VITE_USE_MOCKS !== 'false'

export const apiClient: ApiClient = isMockMode ? createMockApiClient() : createHttpApiClient()

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  setHttpUnauthorizedHandler(handler)
  setMockUnauthorizedHandler(handler)
}

export { DEMO_ACCOUNT_CREDENTIALS, tokenStorage }
export type { ApiClient, AuthApi, LotsApi } from '@/api/types'
