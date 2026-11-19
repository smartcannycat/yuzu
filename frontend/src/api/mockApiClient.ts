import {
  createMockAuthApi,
  DEMO_ACCOUNT_CREDENTIALS,
  MOCK_SESSION_STORAGE_KEY,
  MOCK_USERS_STORAGE_KEY,
  resetMockUsers,
  setMockUnauthorizedHandler,
} from '@/api/mock/auth'
import { createMockProblem, type MockClientOptions } from '@/api/mock/helpers'
import { createMockLotsApi } from '@/api/mock/lots'
import { MOCK_WORKSPACE_STORAGE_KEY, resetMockLotsWorkspace } from '@/api/mock/lotsBatches'
import type { ApiClient, RequestCancelOptions } from '@/api/types'

export {
  DEMO_ACCOUNT_CREDENTIALS,
  MOCK_SESSION_STORAGE_KEY,
  MOCK_USERS_STORAGE_KEY,
  MOCK_WORKSPACE_STORAGE_KEY,
  resetMockLotsWorkspace,
  resetMockUsers,
  setMockUnauthorizedHandler,
  type MockClientOptions,
}

export function createMockApiClient(options: MockClientOptions = {}): ApiClient {
  const defaultDelay = options.delayMs ?? 240
  const persistState = options.persistState ?? false

  return {
    auth: createMockAuthApi(defaultDelay, persistState),
    lots: createMockLotsApi(defaultDelay, persistState),
    media: {
      async fetchBlob(url: string, cancelOptions?: RequestCancelOptions): Promise<Blob> {
        const response = await fetch(url, { signal: cancelOptions?.signal })
        if (!response.ok) {
          throw createMockProblem({
            slug: 'media-not-found',
            title: 'Медиафайл не найден',
            status: response.status,
            detail: 'Не удалось загрузить изображение.',
            instance: url,
          })
        }
        return response.blob()
      },
    },
  }
}
