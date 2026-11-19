import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'

import { useLotFeedActions } from '@/composables/useLotFeedActions'
import type { LotSummary } from '@/types/api'

function makeLot(id: string): LotSummary {
  return {
    lot_id: id,
    make: 'Toyota',
    model: 'Corolla',
    year: 2021,
    engine_cc: 1797,
    frame_id: `ZWE211-${id}`,
    auction_house: 'USS',
    lot_number: id,
    overall_grade: '4.5',
    mileage_km: 32000,
    turnkey_cost_rub: 1850000,
    market_price_rf_rub: 2150000,
    verdict: 'green',
    verdict_headline: 'Можно брать',
    net_benefit_rub: 300000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
    thumbnail_url: null,
    auction_date: null,
    is_archived: false,
    archived_at: null,
    archived_reason: null,
    expires_at: null,
    created_at: '2026-11-10T10:00:00Z',
  }
}

describe('useLotFeedActions', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('commits pending delete safely via onScopeDispose without unhandled rejection', async () => {
    const unhandledSpy = vi.fn()
    window.addEventListener('unhandledrejection', unhandledSpy)

    const items = ref([makeLot('lot-1')])
    const deleteLot = vi.fn().mockRejectedValue(new Error('Network fail'))
    const scope = effectScope()

    const actions = scope.run(() =>
      useLotFeedActions(items, {
        setLotArchived: vi.fn(),
        deleteLot,
        bulkDeleteLots: vi.fn(),
      }),
    )!

    await actions.handleDeleteLot(items.value[0]!)
    expect(actions.pendingDelete.value?.lot.lot_id).toBe('lot-1')

    scope.stop()
    await Promise.resolve()
    await Promise.resolve()

    expect(deleteLot).toHaveBeenCalledWith('lot-1')
    expect(unhandledSpy).not.toHaveBeenCalled()
    window.removeEventListener('unhandledrejection', unhandledSpy)
  })

  it('prevents timer race when handleDeleteLot is called rapidly while previous commit is awaiting', async () => {
    const items = ref([makeLot('lot-1'), makeLot('lot-2'), makeLot('lot-3')])
    let resolveFirstCommit!: () => void
    const deleteLot = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveFirstCommit = resolve
          }),
      )
      .mockResolvedValue(undefined)

    const scope = effectScope()
    const actions = scope.run(() =>
      useLotFeedActions(items, {
        setLotArchived: vi.fn(),
        deleteLot,
        bulkDeleteLots: vi.fn(),
      }),
    )!

    // Start delete 1 (starts 5s timer)
    await actions.handleDeleteLot(items.value[0]!)
    // Start delete 2 (awaits deleteLot('lot-1'))
    const p2 = actions.handleDeleteLot(items.value[1]!)
    // While delete 2 is awaiting deleteLot('lot-1'), user deletes lot-3
    const p3 = actions.handleDeleteLot(items.value[2]!)

    resolveFirstCommit()
    await Promise.all([p2, p3])

    // Only lot-3 should hold the active Undo timer; superseded lot-2 must NOT clobber it.
    expect(actions.pendingDelete.value?.lot.lot_id).toBe('lot-3')

    await vi.advanceTimersByTimeAsync(5000)
    expect(deleteLot).toHaveBeenCalledWith('lot-1')
    expect(deleteLot).toHaveBeenCalledWith('lot-3')
    expect(deleteLot).not.toHaveBeenCalledWith('lot-2')
    scope.stop()
  })

  it('prunes stale selectedLotIds when itemsSource updates', async () => {
    const items = ref([makeLot('lot-1'), makeLot('lot-2'), makeLot('lot-3')])
    const scope = effectScope()
    const actions = scope.run(() =>
      useLotFeedActions(items, {
        setLotArchived: vi.fn(),
        deleteLot: vi.fn(),
        bulkDeleteLots: vi.fn(),
      }),
    )!

    actions.handleStartMultiSelect(items.value[0]!)
    actions.handleToggleSelectLot('lot-2')
    expect(Array.from(actions.selectedLotIds.value)).toEqual(['lot-1', 'lot-2'])

    // Remove lot-2 from itemsSource (e.g., background refresh or archive)
    items.value = [makeLot('lot-1'), makeLot('lot-3')]
    await nextTick()

    expect(Array.from(actions.selectedLotIds.value)).toEqual(['lot-1'])
    scope.stop()
  })
})
