import { createFetch, FetchError, type Fetch, type FetchOptions } from 'ofetch'

import { tokenStorage } from '@/api/tokenStorage'
import {
  ApiError,
  type AuthTokensResponse,
  type InvalidParamDetail,
  type ProblemDetail,
  type TokenRefreshRequest,
} from '@/types/api'

const DEFAULT_BASE_URL = '/api/v1'

export interface HttpClientOptions {
  baseUrl?: string
  fetch?: Fetch
}

export interface InternalRequestOptions extends Omit<FetchOptions<'json'>, 'headers'> {
  headers?: Record<string, string>
  skipAuth?: boolean
  skipRefresh?: boolean
}

export type HttpRequestFn = <T>(path: string, requestOptions?: InternalRequestOptions) => Promise<T>

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

function isInvalidParamArray(value: unknown): value is InvalidParamDetail[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        typeof item === 'object' &&
        item !== null &&
        'name' in item &&
        'reason' in item &&
        typeof item.name === 'string' &&
        typeof item.reason === 'string',
    )
  )
}

function toApiError(error: unknown, path: string): ApiError {
  if (error instanceof ApiError) {
    return error
  }

  if (error instanceof FetchError) {
    const status = error.statusCode ?? error.status ?? 0
    if (status === 0) {
      return new ApiError({
        type: 'about:blank',
        title: 'Нет соединения с сервером',
        status: 0,
        detail: 'Проверьте подключение к сети и повторите попытку.',
        instance: path,
        invalid_params: [],
      })
    }

    const fallbackTitle = error.statusMessage || error.statusText || 'Ошибка сервера'
    const payload: unknown = error.data

    if (typeof payload === 'object' && payload !== null && !Array.isArray(payload)) {
      const record = payload as Record<string, unknown>
      const problem: ProblemDetail = {
        type: typeof record.type === 'string' ? record.type : 'about:blank',
        title: typeof record.title === 'string' ? record.title : fallbackTitle,
        status: typeof record.status === 'number' ? record.status : status,
        detail:
          typeof record.detail === 'string'
            ? record.detail
            : typeof record.message === 'string'
              ? record.message
              : fallbackTitle,
        instance: typeof record.instance === 'string' ? record.instance : path,
        invalid_params: isInvalidParamArray(record.invalid_params) ? record.invalid_params : [],
        timestamp: typeof record.timestamp === 'string' ? record.timestamp : undefined,
      }
      return new ApiError(problem)
    }

    return new ApiError({
      type: 'about:blank',
      title: fallbackTitle,
      status,
      detail:
        status === 401
          ? 'Сессия истекла или указаны неверные учетные данные'
          : `Запрос завершился со статусом ${status}`,
      instance: path,
      invalid_params: [],
    })
  }

  return new ApiError({
    type: 'about:blank',
    title: 'Непредвиденная ошибка',
    status: 0,
    detail: error instanceof Error ? error.message : 'Не удалось выполнить запрос.',
    instance: path,
    invalid_params: [],
  })
}

export function createHttpTransport(options: HttpClientOptions = {}): HttpRequestFn {
  const baseURL = (options.baseUrl ?? getDefaultBaseUrl()).replace(/\/+$/, '')
  const apiFetch = createFetch({
    defaults: {
      baseURL,
      headers: {
        Accept: 'application/json',
      },
      retry: 0,
    },
    ...(options.fetch ? { fetch: options.fetch } : {}),
  })

  let activeRefreshPromise: Promise<boolean> | null = null

  function clearSessionAndNotify(): void {
    tokenStorage.clear()
    unauthorizedHandler?.()
  }

  async function tryRefreshSession(): Promise<boolean> {
    const refreshToken = tokenStorage.getRefreshToken()
    if (!refreshToken) {
      clearSessionAndNotify()
      return false
    }

    if (!activeRefreshPromise) {
      const body: TokenRefreshRequest = { refresh_token: refreshToken }
      activeRefreshPromise = apiFetch<AuthTokensResponse>('/auth/refresh', {
        method: 'POST',
        body,
      })
        .then((tokens) => {
          tokenStorage.setFromAuthResponse(tokens)
          return true
        })
        .catch(() => {
          clearSessionAndNotify()
          return false
        })
        .finally(() => {
          activeRefreshPromise = null
        })
    }

    return activeRefreshPromise
  }

  return async function request<T>(
    path: string,
    requestOptions: InternalRequestOptions = {},
  ): Promise<T> {
    const {
      skipAuth = false,
      skipRefresh = false,
      headers: customHeaders,
      ...fetchOpts
    } = requestOptions

    const headers: Record<string, string> = {
      ...customHeaders,
    }

    const usedAccessToken = skipAuth ? null : tokenStorage.getAccessToken()
    if (usedAccessToken) {
      headers.Authorization = `Bearer ${usedAccessToken}`
    }

    try {
      return await apiFetch<T>(path, {
        ...fetchOpts,
        headers,
      })
    } catch (error: unknown) {
      if (error instanceof FetchError && (error.statusCode ?? error.status) === 401 && !skipAuth) {
        if (!skipRefresh) {
          const latestAccessToken = tokenStorage.getAccessToken()
          if (latestAccessToken && latestAccessToken !== usedAccessToken) {
            return request<T>(path, {
              ...requestOptions,
              skipRefresh: true,
            })
          }

          const refreshed = await tryRefreshSession()
          if (refreshed) {
            return request<T>(path, {
              ...requestOptions,
              skipRefresh: true,
            })
          }
        } else {
          clearSessionAndNotify()
        }
      }

      throw toApiError(error, `${baseURL}${path}`)
    }
  }
}
