import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createMockApiClient } from '@/api/mockApiClient'
import type { ApiClient } from '@/api/types'
import { useLotsStore } from '@/stores/lots'
import type { LotListResponse } from '@/types/api'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('useLotsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads lots from mock client and computes activeFiltersCount', async () => {
    const store = useLotsStore()
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

  it('ignores stale responses via last-write-wins sequence guard', async () => {
    const store = useLotsStore()
    const first = createDeferred<LotListResponse>()
    const second = createDeferred<LotListResponse>()

    const listMock = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const client = {
      auth: createMockApiClient({ delayMs: 0 }).auth,
      lots: { list: listMock },
    } as unknown as ApiClient

    const firstCall = store.fetchLots(client)
    const secondCall = store.fetchLots(client)

    second.resolve({
      items: [
        {
          lot_id: 'newer-lot',
          make: 'Honda',
          model: 'Vezel',
          year: 2021,
          engine_cc: 1496,
          frame_id: 'RV5-1029384',
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
          created_at: '2026-05-31T09:40:00Z',
        },
      ],
      in_progress: { active_batches_count: 0, total_processing_lots: 0, items: [] },
      pagination: { total_items: 1, page: 1, page_size: 20, total_pages: 1 },
      available_filters: {
        total_lots_count: 1,
        makes: [{ value: 'Honda', count: 1 }],
        models: [{ value: 'Vezel', count: 1 }],
        counts_by_verdict: { green: 1 },
      },
    })

    await secondCall

    first.resolve({
      items: [],
      in_progress: { active_batches_count: 0, total_processing_lots: 0, items: [] },
      pagination: { total_items: 0, page: 1, page_size: 20, total_pages: 0 },
      available_filters: { total_lots_count: 0, makes: [], models: [], counts_by_verdict: {} },
    })

    await firstCall

    expect(store.items).toHaveLength(1)
    expect(store.items[0]?.lot_id).toBe('newer-lot')
    expect(store.isLoading).toBe(false)
  })

  it('always resets isLoading when refreshLotsSilently overlaps with fetchLots', async () => {
    const store = useLotsStore()
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

    silentFetch.resolve({
      items: [],
      in_progress: { active_batches_count: 1, total_processing_lots: 1, items: [] },
      pagination: { total_items: 0, page: 1, page_size: 20, total_pages: 0 },
      available_filters: { total_lots_count: 0, makes: [], models: [], counts_by_verdict: {} },
    })
    await silentPromise

    visibleFetch.resolve({
      items: [],
      in_progress: { active_batches_count: 0, total_processing_lots: 0, items: [] },
      pagination: { total_items: 0, page: 1, page_size: 20, total_pages: 0 },
      available_filters: { total_lots_count: 0, makes: [], models: [], counts_by_verdict: {} },
    })
    await visiblePromise

    expect(store.isLoading).toBe(false)
  })

  it('loads lot detail, applies recalculation across store, and resets cleanly to baseline', async () => {
    const client = createMockApiClient({ delayMs: 0 })
    const store = useLotsStore()

    const loaded = await store.fetchLotDetail('892b4e10-3a2c-411f-a801-019283746501', client)
    expect(loaded).not.toBeNull()
    expect(store.isSimulationModified).toBe(false)

    const initialTurnkey = store.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub
    await store.recalculateLot(
      '892b4e10-3a2c-411f-a801-019283746501',
      { is_commercial_util: true, include_repairs: true },
      client,
    )

    expect(store.isSimulationModified).toBe(true)
    expect(store.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub).toBeGreaterThan(
      initialTurnkey,
    )

    store.resetLotSimulation('892b4e10-3a2c-411f-a801-019283746501')
    expect(store.isSimulationModified).toBe(false)
    expect(store.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub).toBe(initialTurnkey)
  })
})
