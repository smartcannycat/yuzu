import {
  createMockAuthApi,
  DEMO_ACCOUNT_CREDENTIALS,
  MOCK_USERS_STORAGE_KEY,
  resetMockUsers,
  setMockUnauthorizedHandler,
} from '@/api/mock/auth'
import type { MockClientOptions } from '@/api/mock/helpers'
import { createMockLotsApi } from '@/api/mock/lots'
import { MOCK_WORKSPACE_STORAGE_KEY, resetMockLotsWorkspace } from '@/api/mock/lotsBatches'
import type { ApiClient } from '@/api/types'

export {
  DEMO_ACCOUNT_CREDENTIALS,
  MOCK_USERS_STORAGE_KEY,
  MOCK_WORKSPACE_STORAGE_KEY,
  resetMockLotsWorkspace,
  resetMockUsers,
  setMockUnauthorizedHandler,
  type MockClientOptions,
}

export function createMockApiClient(options: MockClientOptions = {}): ApiClient {
  const defaultDelay = options.delayMs ?? 240

  return {
    auth: createMockAuthApi(defaultDelay),
    lots: createMockLotsApi(defaultDelay, options.persistState ?? false),
  }
}
