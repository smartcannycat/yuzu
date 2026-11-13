import { ApiError, type InvalidParamDetail } from '@/types/api'

export interface MockClientOptions {
  delayMs?: number
}

export function delay(ms: number): Promise<void> {
  if (ms <= 0) return Promise.resolve()
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export function generateUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const suffix = Math.random().toString(16).slice(2, 14).padEnd(12, '0')
  return `99999999-4444-4888-8999-${suffix}`
}

export function createMockProblem(options: {
  slug: string
  title: string
  status: number
  detail: string
  instance: string
  invalidParams?: InvalidParamDetail[]
}): ApiError {
  return new ApiError({
    type: `https://api.auction-calc.ru/errors/${options.slug}`,
    title: options.title,
    status: options.status,
    detail: options.detail,
    instance: options.instance,
    invalid_params: options.invalidParams ?? [],
    timestamp: new Date().toISOString(),
  })
}
