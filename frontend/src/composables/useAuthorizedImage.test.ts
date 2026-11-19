import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'

import { tokenStorage } from '@/api/tokenStorage'
import type { ApiClient } from '@/api/types'
import { clearAuthorizedImageCache, useAuthorizedImage } from '@/composables/useAuthorizedImage'

async function flushAsync(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('useAuthorizedImage', () => {
  let blobCounter = 0

  beforeEach(() => {
    blobCounter = 0
    clearAuthorizedImageCache()
    tokenStorage.clear()
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
      blobCounter += 1
      return `blob:test/${blobCounter}`
    })
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
  })

  afterEach(() => {
    clearAuthorizedImageCache()
    vi.restoreAllMocks()
  })

  it('passes through data: and blob: URLs in mock mode without fetching', async () => {
    const fetchBlob = vi.fn()
    const client = { media: { fetchBlob } } as unknown as ApiClient

    const dataUrl = 'data:image/svg+xml;charset=utf-8,%3Csvg%3E%3C/svg%3E'
    const urlRef = ref<string | null>(dataUrl)
    const scope = effectScope()
    const state = scope.run(() => useAuthorizedImage(urlRef, { client }))!
    await flushAsync()

    expect(state.src.value).toBe(dataUrl)
    expect(fetchBlob).not.toHaveBeenCalled()

    urlRef.value = 'blob:https://yuzu.local/existing'
    await flushAsync()
    expect(state.src.value).toBe('blob:https://yuzu.local/existing')
    expect(fetchBlob).not.toHaveBeenCalled()

    scope.stop()
  })

  it('fetches protected media via client, caches in LRU, evicts oldest, and revokes on logout', async () => {
    const fetchBlob = vi.fn(async () => new Blob(['img'], { type: 'image/jpeg' }))
    const client = { media: { fetchBlob } } as unknown as ApiClient

    const urlRef = ref<string | null>('/api/v1/lots/1/media/thumbnail')
    const scope = effectScope()
    const state = scope.run(() => useAuthorizedImage(urlRef, { client, maxCacheEntries: 2 }))!
    await flushAsync()

    expect(state.src.value).toBe('blob:test/1')
    expect(fetchBlob).toHaveBeenCalledTimes(1)

    // Load 2nd URL -> cache has [1, 2]
    urlRef.value = '/api/v1/lots/2/media/thumbnail'
    await flushAsync()
    expect(state.src.value).toBe('blob:test/2')

    // Re-visit URL 1 -> cache hit, no new fetch!
    urlRef.value = '/api/v1/lots/1/media/thumbnail'
    await flushAsync()
    expect(state.src.value).toBe('blob:test/1')
    expect(fetchBlob).toHaveBeenCalledTimes(2)

    // Load 3rd URL -> evicts URL 2 (oldest) and revokes blob:test/2
    urlRef.value = '/api/v1/lots/3/media/thumbnail'
    await flushAsync()
    expect(state.src.value).toBe('blob:test/3')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test/2')

    // Session reset (logout) revokes remaining cached URLs and clears src
    tokenStorage.resetSession()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test/1')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test/3')
    expect(state.src.value).toBeUndefined()

    scope.stop()
  })

  it('aborts in-flight fetch on URL change and scope disposal, and defers revoke until unmount when evicted while mounted', async () => {
    const signals: AbortSignal[] = []
    let resolveSecond!: (blob: Blob) => void

    const fetchBlob = vi
      .fn()
      .mockImplementationOnce((_url: string, opts?: { signal?: AbortSignal }) => {
        if (opts?.signal) signals.push(opts.signal)
        return new Promise<Blob>(() => undefined)
      })
      .mockImplementationOnce((_url: string, opts?: { signal?: AbortSignal }) => {
        if (opts?.signal) signals.push(opts.signal)
        return new Promise<Blob>((resolve) => {
          resolveSecond = resolve
        })
      })
      .mockImplementationOnce(async () => new Blob(['img-3'], { type: 'image/jpeg' }))

    const client = { media: { fetchBlob } } as unknown as ApiClient
    const urlRef = ref('/api/v1/lots/10/media/scan')
    const scope1 = effectScope()
    const state1 = scope1.run(() => useAuthorizedImage(urlRef, { client, maxCacheEntries: 1 }))!
    await flushAsync()
    expect(signals[0]?.aborted).toBe(false)

    // Changing URL aborts first pending request
    urlRef.value = '/api/v1/lots/11/media/scan'
    await flushAsync()
    expect(signals[0]?.aborted).toBe(true)
    expect(signals[1]?.aborted).toBe(false)

    resolveSecond(new Blob(['img-2'], { type: 'image/jpeg' }))
    await flushAsync()
    expect(state1.src.value).toBe('blob:test/1')

    // Second scope loads lot 12 -> evicts lot 11 from LRU while scope1 is still mounted!
    const scope2 = effectScope()
    scope2.run(() =>
      useAuthorizedImage('/api/v1/lots/12/media/scan', { client, maxCacheEntries: 1 }),
    )
    await flushAsync()
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:test/1')

    // Disposing scope1 drops ref on evicted entry and revokes it immediately
    scope1.stop()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test/1')

    // Also test abort on scope disposal while pending
    let pendingSignal: AbortSignal | undefined
    const pendingClient = {
      media: {
        fetchBlob: vi.fn((_u: string, opts?: { signal?: AbortSignal }) => {
          pendingSignal = opts?.signal
          return new Promise<Blob>(() => undefined)
        }),
      },
    } as unknown as ApiClient
    const scope3 = effectScope()
    scope3.run(() => useAuthorizedImage('/api/v1/lots/13/media/scan', { client: pendingClient }))
    await flushAsync()
    expect(pendingSignal?.aborted).toBe(false)
    scope3.stop()
    expect(pendingSignal?.aborted).toBe(true)

    scope2.stop()
  })
})
