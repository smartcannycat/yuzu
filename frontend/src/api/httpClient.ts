import { createHttpAuthApi } from '@/api/http/auth'
import { createHttpLotsApi } from '@/api/http/lots'
import {
  createHttpTransport,
  setHttpUnauthorizedHandler,
  type HttpClientOptions,
} from '@/api/http/transport'
import type { ApiClient } from '@/api/types'

export { setHttpUnauthorizedHandler, type HttpClientOptions }

export function createHttpApiClient(options: HttpClientOptions = {}): ApiClient {
  const request = createHttpTransport(options)

  return {
    auth: createHttpAuthApi(request),
    lots: createHttpLotsApi(request),
  }
}
