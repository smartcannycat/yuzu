import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createMockApiClient, resetMockLotsWorkspace } from '@/api/mockApiClient'
import type { ApiClient } from '@/api/types'
import { clampPollIntervalMs, useBatchesStore } from '@/stores/batches'
import { useLotsStore } from '@/stores/lots'
import { ApiError, type BatchProgressResponse } from '@/types/api'

function makeSheetFile(name: string): File {
  return new File(['mock-sheet-bytes'], name, { type: 'image/jpeg' })
}

describe('useBatchesStore & mock batch pipeline', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('creates a batch, updates home in_progress immediately, appends items, and promotes finished lots', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-13T10:00:00Z'))

    const client = createMockApiClient({ delayMs: 0 })
    const lotsStore = useLotsStore()
    const batchesStore = useBatchesStore()

    await lotsStore.fetchLots(client)
    expect(lotsStore.items).toHaveLength(6)
    expect(lotsStore.inProgress.total_processing_lots).toBe(2)

    const created = await batchesStore.createBatch(
      [makeSheetFile('sheet_corolla_3142.jpg'), makeSheetFile('sheet_harrier_5541.jpg')],
      client,
    )

    expect(created.total_items).toBe(2)
    expect(created.status).toBe('queued')
    expect(lotsStore.inProgress.total_processing_lots).toBe(4)

    const initialProgress = await batchesStore.fetchBatch(created.batch_id, {}, client)
    expect(initialProgress?.total_count).toBe(2)
    expect(initialProgress?.status).toMatch(/queued|processing/)
    expect(batchesStore.canAppend).toBe(true)

    const appended = await batchesStore.appendItems(
      created.batch_id,
      [makeSheetFile('sheet_vezel_8412.jpg')],
      client,
    )
    expect(appended.total_count).toBe(3)

    // Advance clock past DAG completion for all items in the batch.
    vi.advanceTimersByTime(10_000)

    const finalProgress = await batchesStore.fetchBatch(created.batch_id, { silent: true }, client)
    expect(finalProgress?.status).toBe('completed')
    expect(finalProgress?.ready_count).toBe(3)
    expect(
      finalProgress?.items.every((item) => item.status === 'ready' && item.summary !== null),
    ).toBe(true)
    expect(batchesStore.isTerminal).toBe(true)

    await lotsStore.refreshLotsSilently(client)
    expect(lotsStore.items.length).toBeGreaterThanOrEqual(9)
    expect(lotsStore.inProgress.total_processing_lots).toBe(0)
  })

  it('protects activeBatch against stale polling responses', async () => {
    const batchesStore = useBatchesStore()

    let resolveFirst!: (val: BatchProgressResponse) => void
    let resolveSecond!: (val: BatchProgressResponse) => void
    const firstPromise = new Promise<BatchProgressResponse>((r) => {
      resolveFirst = r
    })
    const secondPromise = new Promise<BatchProgressResponse>((r) => {
      resolveSecond = r
    })

    const getBatchMock = vi
      .fn()
      .mockReturnValueOnce(firstPromise)
      .mockReturnValueOnce(secondPromise)

    const mockLots = createMockApiClient({ delayMs: 0 }).lots
    const client = {
      auth: createMockApiClient({ delayMs: 0 }).auth,
      lots: {
        ...mockLots,
        getBatch: getBatchMock,
      },
    } as unknown as ApiClient

    const call1 = batchesStore.fetchBatch('batch-1', {}, client)
    const call2 = batchesStore.fetchBatch('batch-1', {}, client)

    resolveSecond({
      batch_id: 'batch-1',
      status: 'completed',
      mascot: { mood: 'happy', phrase_ru: 'Готово', badge_text: '1 из 1 готово' },
      total_count: 1,
      processed_count: 1,
      ready_count: 1,
      failed_count: 0,
      items: [],
    })
    await call2

    resolveFirst({
      batch_id: 'batch-1',
      status: 'processing',
      mascot: { mood: 'thinking', phrase_ru: 'Устаревший ответ', badge_text: '0 из 1 готово' },
      total_count: 1,
      processed_count: 0,
      ready_count: 0,
      failed_count: 0,
      items: [],
    })
    await call1

    expect(batchesStore.activeBatch?.status).toBe('completed')
  })

  it('clamps server poll_interval_ms bounds, tracks error status, and persists mock workspace', async () => {
    expect(clampPollIntervalMs(200)).toBe(800)
    expect(clampPollIntervalMs(999_999_999)).toBe(10_000)
    expect(clampPollIntervalMs(2500)).toBe(2500)
    expect(clampPollIntervalMs(-1)).toBe(1500)

    const batchesStore = useBatchesStore()
    const baseClient = createMockApiClient({ delayMs: 0 })
    const unauthClient = {
      auth: baseClient.auth,
      lots: {
        ...baseClient.lots,
        getBatch: vi.fn().mockRejectedValue(
          new ApiError({
            type: 'about:blank',
            title: 'Unauthorized',
            status: 401,
            detail: 'Session expired',
          }),
        ),
      },
    } as unknown as ApiClient

    const failedResult = await batchesStore.fetchBatch('batch-401', {}, unauthClient)
    expect(failedResult).toBeNull()
    expect(batchesStore.batchErrorStatus).toBe(401)

    // Verify F5 workspace persistence when persistState is enabled.
    resetMockLotsWorkspace()
    const clientBeforeReload = createMockApiClient({ delayMs: 0, persistState: true })
    const created = await clientBeforeReload.lots.createBatch([makeSheetFile('sheet_corolla.jpg')])

    const clientAfterReload = createMockApiClient({ delayMs: 0, persistState: true })
    const restored = await clientAfterReload.lots.getBatch(created.batch_id)
    expect(restored.batch_id).toBe(created.batch_id)
    expect(restored.items).toHaveLength(1)
    resetMockLotsWorkspace()
  })
})
