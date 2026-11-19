import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { createMockApiClient } from '@/api/mockApiClient'
import type { ApiClient } from '@/api/types'
import { useLotDetailStore } from '@/stores/lotDetail'
import { useLotFeedStore } from '@/stores/lotFeed'
import type { LotDetailResponse, RecalculateResponse } from '@/types/api'

function createDeferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('useLotDetailStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads lot detail, applies recalculation across feed & detail, and resets cleanly using structuredClone', async () => {
    const client = createMockApiClient({ delayMs: 0 })
    const feedStore = useLotFeedStore()
    const detailStore = useLotDetailStore()

    await feedStore.fetchLots(client)

    const loaded = await detailStore.fetchLotDetail('892b4e10-3a2c-411f-a801-019283746501', client)
    expect(loaded).not.toBeNull()
    expect(detailStore.isSimulationModified).toBe(false)

    const initialTurnkey = detailStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub
    await detailStore.recalculateLot(
      '892b4e10-3a2c-411f-a801-019283746501',
      { is_commercial_util: true, include_repairs: true },
      client,
    )

    expect(detailStore.isSimulationModified).toBe(true)
    const modifiedTurnkey =
      detailStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub
    expect(modifiedTurnkey).toBeGreaterThan(initialTurnkey)
    expect(
      feedStore.items.find((item) => item.lot_id === '892b4e10-3a2c-411f-a801-019283746501')
        ?.turnkey_cost_rub,
    ).toBe(modifiedTurnkey)

    await detailStore.fetchLotDetail('892b4e10-3a2c-411f-a801-019283746501', client)
    expect(detailStore.isSimulationModified).toBe(true)

    await detailStore.resetLotSimulation('892b4e10-3a2c-411f-a801-019283746501', client)
    expect(detailStore.isSimulationModified).toBe(false)
    expect(detailStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub).toBe(
      initialTurnkey,
    )
    expect(
      feedStore.items.find((item) => item.lot_id === '892b4e10-3a2c-411f-a801-019283746501')
        ?.turnkey_cost_rub,
    ).toBe(initialTurnkey)
  })

  it('aborts previous getDetail via AbortController and ignores stale recalculate responses', async () => {
    const baseClient = createMockApiClient({ delayMs: 0 })
    const detailA = await baseClient.lots.getDetail('892b4e10-3a2c-411f-a801-019283746501')
    const detailB = await baseClient.lots.getDetail('892b4e10-3a2c-411f-a801-019283746504')
    const recalcA = await baseClient.lots.recalculate(detailA.lot_id, { bid_jpy: 2_000_000 })

    const signals: AbortSignal[] = []
    const deferredRecalcA = createDeferred<RecalculateResponse>()
    const deferredDetailA = createDeferred<LotDetailResponse>()
    const deferredDetailB = createDeferred<LotDetailResponse>()

    const getDetailMock = vi
      .fn()
      .mockResolvedValueOnce(detailA)
      .mockImplementationOnce((_id, opts?: { signal?: AbortSignal }) => {
        if (opts?.signal) signals.push(opts.signal)
        return deferredDetailB.promise
      })
      .mockImplementationOnce((_id, opts?: { signal?: AbortSignal }) => {
        if (opts?.signal) signals.push(opts.signal)
        return deferredDetailA.promise
      })

    const recalculateMock = vi.fn().mockReturnValueOnce(deferredRecalcA.promise)

    const client = {
      auth: baseClient.auth,
      lots: {
        list: baseClient.lots.list,
        getDetail: getDetailMock,
        recalculate: recalculateMock,
      },
    } as unknown as ApiClient

    const store = useLotDetailStore()
    await store.fetchLotDetail(detailA.lot_id, client)
    expect(store.currentLotDetail?.lot_id).toBe(detailA.lot_id)

    const recalcPromise = store.recalculateLot(detailA.lot_id, { bid_jpy: 2_000_000 }, client)
    expect(store.isRecalculating).toBe(true)

    const fetchBPromise = store.fetchLotDetail(detailB.lot_id, client)
    expect(store.isRecalculating).toBe(false)

    deferredDetailB.resolve(detailB)
    await fetchBPromise
    expect(store.currentLotDetail?.lot_id).toBe(detailB.lot_id)

    deferredRecalcA.resolve(recalcA)
    const staleRecalcResult = await recalcPromise
    expect(staleRecalcResult).toBeNull()
    expect(store.currentLotDetail?.lot_id).toBe(detailB.lot_id)
    expect(store.isRecalculating).toBe(false)

    const fetchALate = store.fetchLotDetail(detailA.lot_id, client)
    expect(signals[1]?.aborted).toBe(false)
    const fetchBWin = store.fetchLotDetail(detailB.lot_id, {
      ...client,
      lots: {
        ...client.lots,
        getDetail: vi.fn().mockResolvedValueOnce(detailB),
      },
    } as unknown as ApiClient)
    expect(signals[1]?.aborted).toBe(true)

    await fetchBWin
    deferredDetailA.resolve(detailA)
    await fetchALate

    expect(store.currentLotDetail?.lot_id).toBe(detailB.lot_id)
    expect(store.isLoadingDetail).toBe(false)
  })

  it('bounds baselineLotDetailsById LRU cache to 20 entries and syncs archive/delete with feed store', async () => {
    const baseClient = createMockApiClient({ delayMs: 0 })
    const template = await baseClient.lots.getDetail('892b4e10-3a2c-411f-a801-019283746501')

    const getDetailMock = vi.fn(async (id: string) => ({
      ...structuredClone(template),
      lot_id: id,
    }))

    const client = {
      ...baseClient,
      lots: { ...baseClient.lots, getDetail: getDetailMock },
    } as unknown as ApiClient

    const detailStore = useLotDetailStore()
    for (let i = 0; i < 25; i += 1) {
      await detailStore.fetchLotDetail(`lot-${i}`, client)
    }
    expect(detailStore.currentLotDetail?.lot_id).toBe('lot-24')

    // Verify lifecycle archive & delete synchronization across stores.
    const feedStore = useLotFeedStore()
    await feedStore.fetchLots(baseClient)
    const targetId = feedStore.items[0]!.lot_id
    await detailStore.fetchLotDetail(targetId, baseClient)

    await detailStore.setLotArchived(targetId, true, baseClient)
    expect(detailStore.currentLotDetail?.is_archived).toBe(true)
    expect(feedStore.items.some((i) => i.lot_id === targetId)).toBe(false)

    await detailStore.deleteLot(targetId, baseClient)
    expect(detailStore.currentLotDetail).toBeNull()
  })
})
