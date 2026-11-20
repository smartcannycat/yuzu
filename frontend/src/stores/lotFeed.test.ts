import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createMockApiClient } from '@/api/mockApiClient'
import type { ApiClient } from '@/api/types'
import { useLotFeedStore } from '@/stores/lotFeed'
import type { LotListQueryParams, LotListResponse, LotSummary } from '@/types/api'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (err: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function makeSummary(id: string): LotSummary {
  return {
    lot_id: id,
    make: 'Honda',
    model: 'Vezel',
    year: 2021,
    engine_cc: 1496,
    frame_id: `RV5-${id}`,
    auction_house: 'USS',
    lot_number: '8412',
    overall_grade: '4.5',
    mileage_km: 38000,
    turnkey_cost_rub: 1890000,
    market_price_rf_rub: 2140000,
    verdict: 'green',
    verdict_headline: 'Можно брать',
    net_benefit_rub: 250000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
    thumbnail_url: null,
    auction_date: null,
    is_archived: false,
    archived_at: null,
    archived_reason: null,
    expires_at: null,
    created_at: '2026-05-31T09:40:00Z',
  }
}

function makeListResponse(
  items: LotSummary[],
  page = 1,
  totalPages = 1,
  totalItems = items.length,
): LotListResponse {
  return {
    items,
    in_progress: { active_batches_count: 0, total_processing_lots: 0, items: [] },
    pagination: { total_items: totalItems, page, page_size: 20, total_pages: totalPages },
    available_filters: {
      total_lots_count: totalItems,
      archived_lots_count: 0,
      makes: [{ value: 'Honda', count: totalItems }],
      models: [{ value: 'Vezel', count: totalItems }],
      counts_by_verdict: { green: totalItems },
    },
  }
}

describe('useLotFeedStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads lots from mock client and computes activeFiltersCount', async () => {
    const store = useLotFeedStore()
    const client = createMockApiClient({ delayMs: 0 })

    expect(store.hasLoadedOnce).toBe(false)
    await store.fetchLots(client)

    expect(store.hasLoadedOnce).toBe(true)
    expect(store.items).toHaveLength(6)
    expect(store.inProgress.total_processing_lots).toBe(2)
    expect(store.availableFilters.total_lots_count).toBe(6)
    expect(store.activeFiltersCount).toBe(0)

    store.selectedMake = 'Toyota'
    store.selectedVerdict = 'green'
    store.onlyAnomalies = true
    expect(store.activeFiltersCount).toBe(3)
    expect(store.hasAnyActiveFilter).toBe(true)

    await store.fetchLots(client)
    expect(store.items).toHaveLength(0)

    store.onlyAnomalies = false
    await store.fetchLots(client)
    expect(store.items).toHaveLength(1)
    expect(store.items[0]?.model).toBe('Corolla Touring')

    const preview = await store.fetchFilterPreview({ make: 'Toyota' }, client)
    expect(preview?.counts_by_verdict).toEqual({ green: 1, yellow: 0, red: 1 })
    expect(store.items).toHaveLength(1)

    store.resetFilters()
    expect(store.activeFiltersCount).toBe(0)
    expect(store.hasAnyActiveFilter).toBe(false)
  })

  it('aborts previous feed fetch via AbortController and ignores stale responses', async () => {
    const store = useLotFeedStore()
    const signals: AbortSignal[] = []
    const first = createDeferred<LotListResponse>()
    const second = createDeferred<LotListResponse>()

    const listMock = vi
      .fn()
      .mockImplementationOnce((_params, opts?: { signal?: AbortSignal }) => {
        if (opts?.signal) signals.push(opts.signal)
        return first.promise
      })
      .mockImplementationOnce((_params, opts?: { signal?: AbortSignal }) => {
        if (opts?.signal) signals.push(opts.signal)
        return second.promise
      })

    const client = {
      auth: createMockApiClient({ delayMs: 0 }).auth,
      lots: { list: listMock },
    } as unknown as ApiClient

    const firstCall = store.fetchLots(client)
    expect(signals[0]?.aborted).toBe(false)

    const secondCall = store.fetchLots(client)
    expect(signals[0]?.aborted).toBe(true)
    expect(signals[1]?.aborted).toBe(false)

    second.resolve(makeListResponse([makeSummary('newer-lot')]))
    await secondCall

    first.resolve(makeListResponse([]))
    await firstCall

    expect(store.items).toHaveLength(1)
    expect(store.items[0]?.lot_id).toBe('newer-lot')
    expect(store.isLoading).toBe(false)
  })

  it('always resets isLoading when refreshLotsSilently overlaps with fetchLots', async () => {
    const store = useLotFeedStore()
    const visibleFetch = createDeferred<LotListResponse>()
    const silentFetch = createDeferred<LotListResponse>()

    const listMock = vi
      .fn()
      .mockReturnValueOnce(visibleFetch.promise)
      .mockReturnValueOnce(silentFetch.promise)

    const client = {
      auth: createMockApiClient({ delayMs: 0 }).auth,
      lots: { list: listMock },
    } as unknown as ApiClient

    const visiblePromise = store.fetchLots(client)
    expect(store.isLoading).toBe(true)

    const silentPromise = store.refreshLotsSilently(client)

    silentFetch.resolve(makeListResponse([]))
    await silentPromise

    visibleFetch.resolve(makeListResponse([]))
    await visiblePromise

    expect(store.isLoading).toBe(false)
  })

  it('preserves loaded paginated pages when refreshLotsSilently runs (FE-MAJ-02)', async () => {
    const store = useLotFeedStore()
    const page1Initial = makeListResponse([makeSummary('p1-a'), makeSummary('p1-b')], 1, 3, 6)
    const page2Initial = makeListResponse([makeSummary('p2-a'), makeSummary('p2-b')], 2, 3, 6)

    const page1Refreshed = makeListResponse([makeSummary('p1-a-new'), makeSummary('p1-b')], 1, 3, 6)
    const page2Refreshed = makeListResponse([makeSummary('p2-a-new'), makeSummary('p2-b')], 2, 3, 6)

    const listMock = vi.fn(async (params?: LotListQueryParams) => {
      const page = params?.page ?? 1
      if (listMock.mock.calls.length === 1) return page1Initial
      if (listMock.mock.calls.length === 2) return page2Initial
      return page === 1 ? page1Refreshed : page2Refreshed
    })

    const client = {
      auth: createMockApiClient({ delayMs: 0 }).auth,
      lots: { list: listMock },
    } as unknown as ApiClient

    await store.fetchLots(client)
    expect(store.pagination.page).toBe(1)
    expect(store.hasMore).toBe(true)

    await store.loadMore(client)
    expect(store.pagination.page).toBe(2)
    expect(store.items.map((i) => i.lot_id)).toEqual(['p1-a', 'p1-b', 'p2-a', 'p2-b'])

    await store.refreshLotsSilently(client)
    expect(store.pagination.page).toBe(2)
    expect(store.hasMore).toBe(true)
    expect(store.items.map((i) => i.lot_id)).toEqual(['p1-a-new', 'p1-b', 'p2-a-new', 'p2-b'])
  })

  it('guards setLotArchived, deleteLot, and bulkDeleteLots across sessionEpoch resets (FE-MAJ-02)', async () => {
    const store = useLotFeedStore()
    const baseClient = createMockApiClient({ delayMs: 0 })

    const archiveDeferred = createDeferred<LotSummary>()
    const deleteDeferred = createDeferred<void>()
    const client = {
      auth: baseClient.auth,
      lots: {
        ...baseClient.lots,
        updateLifecycle: vi.fn().mockReturnValue(archiveDeferred.promise),
        deleteLot: vi.fn().mockReturnValue(deleteDeferred.promise),
      },
    } as unknown as ApiClient

    store.items = [makeSummary('lot-1')]
    store.hasLoadedOnce = true

    const archiveOp = store.setLotArchived('lot-1', true, client)
    store.clear() // sessionEpoch increments before await settles
    archiveDeferred.resolve({ ...makeSummary('lot-1'), is_archived: true })
    await archiveOp
    expect(store.items).toHaveLength(0)

    store.items = [makeSummary('lot-2')]
    const deleteOp = store.deleteLot('lot-2', client)
    store.clear()
    deleteDeferred.resolve()
    await deleteOp
    expect(store.items).toHaveLength(0)
  })

  it('removes successfully deleted chunks locally even when a subsequent bulkDeleteLots chunk fails (FE-MAJ-02)', async () => {
    const store = useLotFeedStore()
    const baseClient = createMockApiClient({ delayMs: 0 })

    const ids = Array.from({ length: 105 }, (_, i) => `lot-${i}`)
    store.items = ids.map((id) => makeSummary(id))

    const bulkMock = vi
      .fn()
      .mockResolvedValueOnce({
        deleted_ids: ids.slice(0, 100),
        not_found_ids: [],
        deleted_count: 100,
      })
      .mockRejectedValueOnce(new Error('Chunk 2 failed'))

    const client = {
      auth: baseClient.auth,
      lots: { ...baseClient.lots, bulkDeleteLots: bulkMock },
    } as unknown as ApiClient

    await expect(store.bulkDeleteLots(ids, client)).rejects.toThrow('Chunk 2 failed')
    expect(bulkMock).toHaveBeenCalledTimes(2)
    expect(store.items.map((item) => item.lot_id)).toEqual(ids.slice(100))
  })

  it('tracks lifecycle filter count, archives/unarchives lots, and chunks bulk deletes', async () => {
    const client = createMockApiClient({ delayMs: 0 })
    const store = useLotFeedStore()

    await store.fetchLots(client)
    expect(store.items).toHaveLength(6)
    expect(store.availableFilters.archived_lots_count).toBe(2)

    const targetId = store.items[0]!.lot_id
    await store.setLotArchived(targetId, true, client)
    expect(store.items).toHaveLength(5)
    expect(store.availableFilters.archived_lots_count).toBe(3)

    store.lifecycle = 'archived'
    expect(store.activeFiltersCount).toBe(1)
    await store.fetchLots(client)
    expect(store.items.length).toBe(3)

    await store.setLotArchived(targetId, false, client)
    expect(store.items).toHaveLength(2)

    store.resetFilters()
    await store.fetchLots(client)
    await store.deleteLot(targetId, client)
    expect(store.items.some((item) => item.lot_id === targetId)).toBe(false)
  })
})
