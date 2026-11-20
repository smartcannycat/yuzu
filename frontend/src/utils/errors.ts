import { ApiError } from '@/types/common'

/**
 * Extracts a safe non-empty display error message from an unknown thrown value.
 */
export function extractApiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const detail = err.detail.trim()
    if (detail) return detail
    const message = err.message.trim()
    if (message) return message
    const title = err.title.trim()
    if (title) return title
    return fallback
  }

  if (err instanceof Error) {
    const message = err.message.trim()
    if (message) return message
  }

  return fallback
}

export const getErrorMessage = extractApiErrorMessage
