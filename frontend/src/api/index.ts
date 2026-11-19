import { createHttpApiClient, setHttpUnauthorizedHandler } from '@/api/httpClient'
import { tokenStorage } from '@/api/tokenStorage'
import type { ApiClient } from '@/api/types'

// Fail closed in production builds: mock mode requires explicit VITE_USE_MOCKS=true.
export const isMockMode = import.meta.env.PROD
  ? import.meta.env.VITE_USE_MOCKS === 'true'
  : import.meta.env.VITE_USE_MOCKS !== 'false'

let latestUnauthorizedHandler: (() => void) | null = null
let mockUnauthorizedSetter: ((handler: (() => void) | null) => void) | null = null

function createLazyMockApiClient(): ApiClient {
  let mockClientPromise: Promise<ApiClient> | null = null

  function loadMockClient(): Promise<ApiClient> {
    if (!mockClientPromise) {
      mockClientPromise = import('@/api/mockApiClient').then((mod) => {
        mockUnauthorizedSetter = mod.setMockUnauthorizedHandler
        mod.setMockUnauthorizedHandler(latestUnauthorizedHandler)
        return mod.createMockApiClient({ persistState: true })
      })
    }
    return mockClientPromise
  }

  void loadMockClient()

  return {
    auth: {
      register: async (payload) => (await loadMockClient()).auth.register(payload),
      login: async (payload) => (await loadMockClient()).auth.login(payload),
      refresh: async () => (await loadMockClient()).auth.refresh(),
      logout: async () => (await loadMockClient()).auth.logout(),
      me: async () => (await loadMockClient()).auth.me(),
    },
    lots: {
      list: async (params, options) => (await loadMockClient()).lots.list(params, options),
      getDetail: async (lotId, options) => (await loadMockClient()).lots.getDetail(lotId, options),
      recalculate: async (lotId, payload) =>
        (await loadMockClient()).lots.recalculate(lotId, payload),
      resetSimulation: async (lotId) => (await loadMockClient()).lots.resetSimulation(lotId),
      updateLifecycle: async (lotId, payload) =>
        (await loadMockClient()).lots.updateLifecycle(lotId, payload),
      deleteLot: async (lotId) => (await loadMockClient()).lots.deleteLot(lotId),
      bulkDeleteLots: async (payload) => (await loadMockClient()).lots.bulkDeleteLots(payload),
      createBatch: async (files) => (await loadMockClient()).lots.createBatch(files),
      getBatch: async (batchId) => (await loadMockClient()).lots.getBatch(batchId),
      appendBatchItems: async (batchId, files) =>
        (await loadMockClient()).lots.appendBatchItems(batchId, files),
    },
    media: {
      fetchBlob: async (url, options) => (await loadMockClient()).media.fetchBlob(url, options),
    },
  }
}

export const apiClient: ApiClient = isMockMode ? createLazyMockApiClient() : createHttpApiClient()

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  latestUnauthorizedHandler = handler
  if (isMockMode) {
    if (mockUnauthorizedSetter) {
      mockUnauthorizedSetter(handler)
    } else {
      void import('@/api/mockApiClient').then((mod) => {
        mockUnauthorizedSetter = mod.setMockUnauthorizedHandler
        mod.setMockUnauthorizedHandler(latestUnauthorizedHandler)
      })
    }
    return
  }
  setHttpUnauthorizedHandler(handler)
}

export { tokenStorage }
export type { ApiClient, AuthApi, LotsApi, MediaApi } from '@/api/types'
