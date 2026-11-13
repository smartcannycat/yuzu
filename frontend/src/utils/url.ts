const ALLOWED_EXTERNAL_PROTOCOLS = new Set(['http:', 'https:'])
const ALLOWED_IMAGE_PROTOCOLS = new Set(['http:', 'https:', 'blob:'])
const SAFE_DATA_IMAGE_PATTERN =
  /^data:image\/(?:png|jpeg|jpg|webp|gif|svg\+xml)(?:;charset=[a-z0-9-]+)?(?:;base64)?,(.+)$/i

function hasControlCharacters(value: string): boolean {
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i)
    if (code <= 0x1f || code === 0x7f) {
      return true
    }
  }
  return false
}

function isSafeRelativePath(value: string): boolean {
  return value.startsWith('/') && !value.startsWith('//')
}

/**
 * Validates external navigation URLs, permitting only http(s) schemes without control characters.
 */
export function sanitizeExternalUrl(rawUrl: string | null | undefined): string | undefined {
  if (typeof rawUrl !== 'string') return undefined
  const trimmed = rawUrl.trim()
  if (!trimmed || hasControlCharacters(trimmed)) return undefined

  try {
    const parsed = new URL(trimmed)
    if (!ALLOWED_EXTERNAL_PROTOCOLS.has(parsed.protocol)) {
      return undefined
    }
    return parsed.toString()
  } catch {
    return undefined
  }
}

/**
 * Validates link href values, permitting http(s) URLs or single-slash relative app paths.
 */
export function sanitizeNavigationHref(rawHref: string | null | undefined): string | undefined {
  if (typeof rawHref !== 'string') return undefined
  const trimmed = rawHref.trim()
  if (!trimmed || hasControlCharacters(trimmed)) return undefined

  if (isSafeRelativePath(trimmed)) {
    return trimmed
  }

  return sanitizeExternalUrl(trimmed)
}

/**
 * Validates image src values, permitting http(s), blob, safe relative paths, and image data URIs.
 */
export function sanitizeImageUrl(rawUrl: string | null | undefined): string | undefined {
  if (typeof rawUrl !== 'string') return undefined
  const trimmed = rawUrl.trim()
  if (!trimmed || hasControlCharacters(trimmed)) return undefined

  if (isSafeRelativePath(trimmed)) {
    return trimmed
  }

  if (trimmed.slice(0, 5).toLowerCase() === 'data:') {
    return SAFE_DATA_IMAGE_PATTERN.test(trimmed) ? trimmed : undefined
  }

  try {
    const parsed = new URL(trimmed)
    if (!ALLOWED_IMAGE_PROTOCOLS.has(parsed.protocol)) {
      return undefined
    }
    return parsed.toString()
  } catch {
    return undefined
  }
}
