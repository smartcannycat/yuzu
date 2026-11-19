import { createFetch, FetchError, type Fetch, type FetchOptions } from 'ofetch'

import { isAbortError, resolveApiRelativePath, toApiError } from '@/api/http/errors'
import { tokenStorage } from '@/api/tokenStorage'
import { ApiError, type AuthTokensResponse } from '@/types/api'

export { isAbortError }

const DEFAULT_BASE_URL = '/api/v1'
const SPA_REQUESTED_WITH_HEADER = 'YuzuSPA'

export interface HttpClientOptions {
  baseUrl?: string
  fetch?: Fetch
}

export interface InternalRequestOptions extends Omit<FetchOptions<'json'>, 'headers'> {
  headers?: Record<string, string>
  skipAuth?: boolean
  skipRefresh?: boolean
}

export interface HttpTransport {
  request<T>(path: string, requestOptions?: InternalRequestOptions): Promise<T>
  fetchBlob(url: string, signal?: AbortSignal): Promise<Blob>
}

export type HttpRequestFn = HttpTransport['request']

let unauthorizedHandler: (() => void) | null = null

export function setHttpUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

function getDefaultBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (typeof configured === 'string' && configured.trim().length > 0) {
    return configured.replace(/\/+$/, '')
  }
  return DEFAULT_BASE_URL
}

interface RefreshAttemptResult {
  ok: boolean
  error?: unknown
}

export function createHttpTransport(options: HttpClientOptions = {}): HttpTransport {
  const baseURL = (options.baseUrl ?? getDefaultBaseUrl()).replace(/\/+$/, '')
  const rawFetch = options.fetch ?? globalThis.fetch
  const apiFetch = createFetch({
    defaults: {
      baseURL,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': SPA_REQUESTED_WITH_HEADER,
      },
      retry: 0,
    },
    ...(options.fetch ? { fetch: options.fetch } : {}),
  })

  let activeRefresh: { gen: number; promise: Promise<RefreshAttemptResult> } | null = null

  function clearSessionAndNotify(): void {
    tokenStorage.clear({ broadcast: true })
    unauthorizedHandler?.()
  }

  async function tryRefreshSession(
    expectedGen: number,
    expectedUserId: string | null,
  ): Promise<RefreshAttemptResult> {
    if (activeRefresh && activeRefresh.gen === expectedGen) {
      return activeRefresh.promise
    }

    const promise = apiFetch<AuthTokensResponse>('/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': SPA_REQUESTED_WITH_HEADER,
      },
    })
      .then((tokens): RefreshAttemptResult => {
        if (tokenStorage.getSessionGen() !== expectedGen) {
          return { ok: false }
        }
        if (expectedUserId !== null && tokens.user.user_id !== expectedUserId) {
          clearSessionAndNotify()
          return { ok: false }
        }
        tokenStorage.setFromAuthResponse(tokens)
        return { ok: true }
      })
      .catch((refreshError: unknown): RefreshAttemptResult => {
        if (isAbortError(refreshError)) {
          return { ok: false, error: refreshError }
        }
        const refreshStatus =
          refreshError instanceof FetchError
            ? (refreshError.statusCode ?? refreshError.status ?? 0)
            : 0
        if (
          (refreshStatus === 401 || refreshStatus === 403) &&
          tokenStorage.getSessionGen() === expectedGen
        ) {
          clearSessionAndNotify()
        }
        return { ok: false, error: refreshError }
      })
      .finally(() => {
        if (activeRefresh?.promise === promise) {
          activeRefresh = null
        }
      })

    activeRefresh = { gen: expectedGen, promise }
    return promise
  }

  async function executeWithRefresh<T>(
    path: string,
    optionsBag: {
      skipAuth: boolean
      skipRefresh: boolean
      signal?: AbortSignal
      run: (headers: Record<string, string>) => Promise<T>
      customHeaders?: Record<string, string>
    },
  ): Promise<T> {
    const headers: Record<string, string> = {
      'X-Requested-With': SPA_REQUESTED_WITH_HEADER,
      ...optionsBag.customHeaders,
    }

    const startGen = tokenStorage.getSessionGen()
    const startUserId = tokenStorage.getUser()?.user_id ?? null
    const usedAccessToken = optionsBag.skipAuth ? null : tokenStorage.getAccessToken()
    if (usedAccessToken) {
      headers.Authorization = `Bearer ${usedAccessToken}`
    }

    try {
      return await optionsBag.run(headers)
    } catch (error: unknown) {
      if (isAbortError(error) || optionsBag.signal?.aborted) {
        throw error
      }

      if (
        error instanceof FetchError &&
        (error.statusCode ?? error.status) === 401 &&
        !optionsBag.skipAuth
      ) {
        const currentGen = tokenStorage.getSessionGen()
        const currentUserId = tokenStorage.getUser()?.user_id ?? null
        const sameSession =
          currentGen === startGen && (startUserId === null || currentUserId === startUserId)

        if (!sameSession) {
          throw toApiError(error, `${baseURL}${path}`)
        }

        if (!optionsBag.skipRefresh) {
          const latestAccessToken = tokenStorage.getAccessToken()
          if (latestAccessToken && latestAccessToken !== usedAccessToken) {
            return executeWithRefresh(path, { ...optionsBag, skipRefresh: true })
          }

          const refreshResult = await tryRefreshSession(startGen, startUserId)
          const afterGen = tokenStorage.getSessionGen()
          const afterUserId = tokenStorage.getUser()?.user_id ?? null
          const stillSameSession =
            afterGen === startGen && (startUserId === null || afterUserId === startUserId)

          if (!refreshResult.ok || !stillSameSession) {
            throw toApiError(refreshResult.error ?? error, `${baseURL}${path}`)
          }

          return executeWithRefresh(path, { ...optionsBag, skipRefresh: true })
        }

        clearSessionAndNotify()
      }

      throw toApiError(error, `${baseURL}${path}`)
    }
  }

  async function request<T>(path: string, requestOptions: InternalRequestOptions = {}): Promise<T> {
    const {
      skipAuth = false,
      skipRefresh = false,
      headers: customHeaders,
      ...fetchOpts
    } = requestOptions

    return executeWithRefresh<T>(path, {
      skipAuth,
      skipRefresh,
      signal: fetchOpts.signal ?? undefined,
      customHeaders,
      run: (headers) =>
        apiFetch<T>(path, {
          ...fetchOpts,
          credentials: 'include',
          headers,
        }),
    })
  }

  async function fetchBlob(url: string, signal?: AbortSignal): Promise<Blob> {
    const apiPath = resolveApiRelativePath(url, baseURL)
    if (apiPath !== null) {
      return executeWithRefresh<Blob>(apiPath, {
        skipAuth: false,
        skipRefresh: false,
        signal,
        customHeaders: { Accept: 'image/*,*/*;q=0.8' },
        run: (headers) =>
          apiFetch<Blob, 'blob'>(apiPath, {
            method: 'GET',
            credentials: 'include',
            responseType: 'blob',
            headers,
            signal,
          }),
      })
    }

    // Non-API or external image URLs never receive Bearer authorization headers.
    const response = await rawFetch(url, {
      method: 'GET',
      credentials: url.startsWith('/') ? 'same-origin' : 'omit',
      signal,
    })
    if (!response.ok) {
      throw new ApiError({
        type: 'about:blank',
        title: response.statusText || 'Ошибка загрузки изображения',
        status: response.status,
        detail: `Не удалось загрузить изображение (${response.status}).`,
        instance: url,
        invalid_params: [],
      })
    }
    return response.blob()
  }

  return {
    request,
    fetchBlob,
  }
}
