import { onScopeDispose, readonly, ref, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

import { apiClient, type ApiClient } from '@/api'
import { tokenStorage } from '@/api/tokenStorage'
import { onSessionReset } from '@/utils/sessionEvents'
import { sanitizeImageUrl } from '@/utils/url'

const DEFAULT_MAX_CACHE_ENTRIES = 40

interface ImageCacheEntry {
  objectUrl: string
  refs: number
  evicted: boolean
  sessionGen: number
}

interface InFlightImageRequest {
  controller: AbortController
  waiters: number
  promise: Promise<string>
}

const imageCache = new Map<string, ImageCacheEntry>()
const inFlightRequests = new Map<string, InFlightImageRequest>()
const activeResetCallbacks = new Set<() => void>()

function revokeEntryIfUnused(key: string, entry: ImageCacheEntry): void {
  if (entry.refs > 0) return
  if (entry.evicted || !imageCache.has(key)) {
    URL.revokeObjectURL(entry.objectUrl)
  }
}

function evictOverflowEntries(maxEntries: number): void {
  while (imageCache.size > maxEntries) {
    const oldest = imageCache.entries().next().value
    if (!oldest) break
    const [oldestKey, oldestEntry] = oldest
    imageCache.delete(oldestKey)
    oldestEntry.evicted = true
    revokeEntryIfUnused(oldestKey, oldestEntry)
  }
}

/**
 * Revokes all cached object URLs, aborts in-flight image fetches, and notifies mounted instances.
 */
export function clearAuthorizedImageCache(): void {
  for (const request of inFlightRequests.values()) {
    request.controller.abort()
  }
  inFlightRequests.clear()

  for (const entry of imageCache.values()) {
    entry.evicted = true
    URL.revokeObjectURL(entry.objectUrl)
  }
  imageCache.clear()

  for (const resetCallback of Array.from(activeResetCallbacks)) {
    resetCallback()
  }
}

onSessionReset('authorizedImageCache', clearAuthorizedImageCache, { global: true })

export interface UseAuthorizedImageOptions {
  maxCacheEntries?: number
  client?: ApiClient
}

export interface UseAuthorizedImageResult {
  src: Readonly<Ref<string | undefined>>
  isLoading: Readonly<Ref<boolean>>
  hasError: Readonly<Ref<boolean>>
}

/**
 * Resolves a protected image URL into an authorized Blob object URL backed by a bounded LRU cache,
 * aborting in-flight fetches on change/unmount and revoking object URLs on session reset or eviction.
 */
export function useAuthorizedImage(
  urlSource: MaybeRefOrGetter<string | null | undefined>,
  options: UseAuthorizedImageOptions = {},
): UseAuthorizedImageResult {
  const maxEntries = Math.max(1, options.maxCacheEntries ?? DEFAULT_MAX_CACHE_ENTRIES)
  const client = options.client ?? apiClient

  const src = ref<string | undefined>(undefined)
  const isLoading = ref(false)
  const hasError = ref(false)

  let activeCacheKey: string | null = null
  let activeEntry: ImageCacheEntry | null = null
  let activeLoadToken = 0
  let pendingCancel: (() => void) | null = null
  let isDisposed = false

  function releaseActiveEntry(): void {
    const key = activeCacheKey
    const entry = activeEntry ?? (key ? imageCache.get(key) : undefined) ?? null
    activeCacheKey = null
    activeEntry = null
    if (!entry) return

    entry.refs = Math.max(0, entry.refs - 1)
    if (entry.refs === 0 && (entry.evicted || entry.sessionGen !== tokenStorage.getSessionGen())) {
      if (key && imageCache.get(key) === entry) {
        imageCache.delete(key)
      }
      URL.revokeObjectURL(entry.objectUrl)
    }
  }

  function cancelPendingFetch(): void {
    pendingCancel?.()
    pendingCancel = null
  }

  function resetCurrentState(): void {
    activeLoadToken += 1
    cancelPendingFetch()
    activeCacheKey = null
    activeEntry = null
    src.value = undefined
    isLoading.value = false
    hasError.value = false
  }

  activeResetCallbacks.add(resetCurrentState)

  async function loadUrl(rawUrl: string | null | undefined): Promise<void> {
    const loadToken = ++activeLoadToken
    cancelPendingFetch()
    releaseActiveEntry()
    hasError.value = false

    const sanitized = sanitizeImageUrl(rawUrl)
    if (!sanitized) {
      src.value = undefined
      isLoading.value = false
      return
    }

    // Pass through inline mock data URLs and pre-created blob URLs without HTTP fetch.
    if (sanitized.startsWith('data:') || sanitized.startsWith('blob:')) {
      src.value = sanitized
      isLoading.value = false
      return
    }

    const sessionGen = tokenStorage.getSessionGen()
    const cacheKey = `${sessionGen}:${sanitized}`
    const cached = imageCache.get(cacheKey)
    if (cached && !cached.evicted) {
      imageCache.delete(cacheKey)
      imageCache.set(cacheKey, cached)
      cached.refs += 1
      activeCacheKey = cacheKey
      activeEntry = cached
      src.value = cached.objectUrl
      isLoading.value = false
      return
    }

    isLoading.value = true
    src.value = undefined

    let inFlight = inFlightRequests.get(cacheKey)
    if (!inFlight) {
      const controller = new AbortController()
      const promise = client.media
        .fetchBlob(sanitized, { signal: controller.signal })
        .then((blob) => {
          if (controller.signal.aborted || tokenStorage.getSessionGen() !== sessionGen) {
            throw new DOMException('Aborted', 'AbortError')
          }
          const objectUrl = URL.createObjectURL(blob)
          const entry: ImageCacheEntry = {
            objectUrl,
            refs: 0,
            evicted: false,
            sessionGen,
          }
          imageCache.set(cacheKey, entry)
          evictOverflowEntries(maxEntries)
          return objectUrl
        })
        .finally(() => {
          if (inFlightRequests.get(cacheKey) === inFlight) {
            inFlightRequests.delete(cacheKey)
          }
        })

      inFlight = { controller, waiters: 0, promise }
      inFlightRequests.set(cacheKey, inFlight)
    }

    inFlight.waiters += 1
    let releasedWaiter = false
    pendingCancel = () => {
      if (releasedWaiter || !inFlight) return
      releasedWaiter = true
      inFlight.waiters = Math.max(0, inFlight.waiters - 1)
      if (inFlight.waiters === 0) {
        inFlight.controller.abort()
        if (inFlightRequests.get(cacheKey) === inFlight) {
          inFlightRequests.delete(cacheKey)
        }
      }
    }

    try {
      const objectUrl = await inFlight.promise
      if (
        isDisposed ||
        loadToken !== activeLoadToken ||
        tokenStorage.getSessionGen() !== sessionGen
      ) {
        return
      }

      const entry = imageCache.get(cacheKey)
      if (entry && !entry.evicted) {
        entry.refs += 1
        activeCacheKey = cacheKey
        activeEntry = entry
      }
      src.value = objectUrl
    } catch {
      if (isDisposed || loadToken !== activeLoadToken) return
      src.value = undefined
      hasError.value = true
    } finally {
      pendingCancel = null
      if (!isDisposed && loadToken === activeLoadToken) {
        isLoading.value = false
      }
    }
  }

  watch(
    () => toValue(urlSource),
    (nextUrl) => {
      void loadUrl(nextUrl)
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    isDisposed = true
    activeLoadToken += 1
    activeResetCallbacks.delete(resetCurrentState)
    cancelPendingFetch()
    releaseActiveEntry()
  })

  return {
    src: readonly(src),
    isLoading: readonly(isLoading),
    hasError: readonly(hasError),
  }
}
