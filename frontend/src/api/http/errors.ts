import { FetchError } from 'ofetch'

import { ApiError, type InvalidParamDetail, type ProblemDetail } from '@/types/api'

export function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true
  }
  if (error instanceof Error && error.name === 'AbortError') {
    return true
  }
  if (error instanceof FetchError && error.cause) {
    return isAbortError(error.cause)
  }
  return false
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

export function toApiError(error: unknown, path: string): ApiError {
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
      const title =
        typeof record.title === 'string' && record.title.trim().length > 0
          ? record.title.trim()
          : fallbackTitle
      const detail =
        typeof record.detail === 'string' && record.detail.trim().length > 0
          ? record.detail.trim()
          : typeof record.message === 'string' && record.message.trim().length > 0
            ? record.message.trim()
            : title
      const problem: ProblemDetail = {
        type: typeof record.type === 'string' ? record.type : 'about:blank',
        title,
        status: typeof record.status === 'number' ? record.status : status,
        detail,
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
    detail:
      error instanceof Error && error.message ? error.message : 'Не удалось выполнить запрос.',
    instance: path,
    invalid_params: [],
  })
}

export function resolveApiRelativePath(url: string, baseURL: string): string | null {
  const baseParsed = new URL(baseURL, 'https://app.local')
  const basePath = baseParsed.pathname.replace(/\/+$/, '')
  const targetParsed = new URL(url, 'https://app.local')

  if (url.startsWith('/')) {
    if (basePath && targetParsed.pathname.startsWith(`${basePath}/`)) {
      return `${targetParsed.pathname.slice(basePath.length)}${targetParsed.search}`
    }
    if (targetParsed.pathname.startsWith('/lots/')) {
      return `${targetParsed.pathname}${targetParsed.search}`
    }
    return null
  }

  if (targetParsed.origin === baseParsed.origin) {
    if (basePath && targetParsed.pathname.startsWith(`${basePath}/`)) {
      return `${targetParsed.pathname.slice(basePath.length)}${targetParsed.search}`
    }
  }

  return null
}
