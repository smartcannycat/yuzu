import { describe, expect, it } from 'vitest'

import { buildMockLotDetail } from '@/api/mock/lotDetails'
import {
  COMMERCIAL_UTIL_BULLET,
  JPY_RUB_RATE,
  MIN_BID_JPY,
  recalculateMockLotDetail,
} from '@/api/mock/lotEconomicsCalc'
import { persistMockDetail } from '@/api/mock/lots'
import { createMockLotsWorkspace, validateUploadFilesForMock } from '@/api/mock/lotsBatches'
import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import { createMockApiClient } from '@/api/mockApiClient'
import { ApiError } from '@/types/api'

describe('mock calculator and validation invariants (FE-MAJ-08)', () => {
  it('makes commercial util bullet add/remove idempotent across repeated recalculations', () => {
    const base = buildMockLotDetail(SEEDED_MOCK_LOTS[0]!)
    expect(base.verdict.reasoning_bullets).not.toContain(COMMERCIAL_UTIL_BULLET)

    let current = base
    for (let i = 0; i < 4; i += 1) {
      const res = recalculateMockLotDetail(current, {
        bid_jpy: current.economics.wise_cost_ladder.car_bid_jpy + 10_000,
        is_commercial_util: true,
      })
      const matches = res.verdict.reasoning_bullets.filter(
        (bullet) => bullet === COMMERCIAL_UTIL_BULLET,
      )
      expect(matches).toHaveLength(1)
      current = {
        ...current,
        verdict: res.verdict,
        economics: {
          ...current.economics,
          customs: res.customs,
          wise_cost_ladder: res.wise_cost_ladder,
        },
      }
    }

    const reverted = recalculateMockLotDetail(current, {
      is_commercial_util: false,
    })
    expect(reverted.is_commercial_util).toBe(false)
    expect(reverted.verdict.reasoning_bullets).not.toContain(COMMERCIAL_UTIL_BULLET)
  })

  it('aligns carBidJpy with 100,000 JPY floor and carBidRub == Math.round(carBidJpy * jpyRate)', () => {
    for (const summary of SEEDED_MOCK_LOTS) {
      const detail = buildMockLotDetail(summary)
      const ladder = detail.economics.wise_cost_ladder
      const rate = detail.economics.customs.rates_snapshot.jpy_rub_bank

      expect(ladder.car_bid_jpy).toBeGreaterThanOrEqual(MIN_BID_JPY)
      expect(ladder.car_bid_rub).toBe(Math.round(ladder.car_bid_jpy * rate))
      const stepsSum = ladder.steps.reduce((acc, step) => acc + step.amount_rub, 0)
      expect(stepsSum).toBe(ladder.turnkey_cost_rub)
    }

    const lowBidSummary = {
      ...SEEDED_MOCK_LOTS[0]!,
      lot_id: '00000000-0000-4000-8000-000000000999',
      turnkey_cost_rub: 200_000,
    }
    const floorDetail = buildMockLotDetail(lowBidSummary)
    expect(floorDetail.economics.wise_cost_ladder.car_bid_jpy).toBe(MIN_BID_JPY)
    expect(floorDetail.economics.wise_cost_ladder.car_bid_rub).toBe(
      Math.round(MIN_BID_JPY * JPY_RUB_RATE),
    )
    expect(floorDetail.economics.bid_slider_min_jpy).toBe(MIN_BID_JPY)
  })

  it('syncs power_hp, power_hp_source, is_under_160_hp, and feed summary fields via persistMockDetail', async () => {
    const workspace = createMockLotsWorkspace()
    const detailCache = new Map()
    const summary = SEEDED_MOCK_LOTS[4]!
    const initial = buildMockLotDetail(summary)
    const recalc = recalculateMockLotDetail(initial, {
      custom_power_hp: 150,
      is_commercial_util: false,
    })

    const persisted = persistMockDetail(initial, recalc, detailCache, workspace)
    expect(persisted.passport.power_hp).toBe(150)
    expect(persisted.passport.power_hp_source).toBe('manual')
    expect(persisted.passport.is_under_160_hp).toBe(true)

    const feedItem = workspace.getFeedSnapshot().lots.find((item) => item.lot_id === summary.lot_id)
    expect(feedItem?.turnkey_cost_rub).toBe(recalc.turnkey_cost_rub)
    expect(feedItem?.net_benefit_rub).toBe(recalc.net_benefit_rub)
    expect(feedItem?.verdict).toBe(recalc.verdict.verdict)

    const client = createMockApiClient({ delayMs: 0 })
    await client.lots.recalculate(summary.lot_id, {
      custom_power_hp: 150,
      is_commercial_util: false,
    })
    const reloaded = await client.lots.getDetail(summary.lot_id)
    expect(reloaded.passport.power_hp).toBe(150)
    expect(reloaded.passport.power_hp_source).toBe('manual')
    expect(reloaded.passport.is_under_160_hp).toBe(true)

    const listRes = await client.lots.list()
    const listedItem = listRes.items.find((item) => item.lot_id === summary.lot_id)
    expect(listedItem?.turnkey_cost_rub).toBe(reloaded.economics.wise_cost_ladder.turnkey_cost_rub)
  })

  it('rejects 0-byte files in validateUploadFilesForMock while accepting valid images', () => {
    const emptyFile = new File([], 'empty.jpg', { type: 'image/jpeg' })
    expect(() => validateUploadFilesForMock([emptyFile], '/api/v1/lots/batches')).toThrow(ApiError)

    try {
      validateUploadFilesForMock([emptyFile], '/api/v1/lots/batches')
    } catch (error: unknown) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(400)
    }

    const validFile = new File([new Uint8Array([1, 2, 3])], 'sheet.jpg', { type: 'image/jpeg' })
    expect(() => validateUploadFilesForMock([validFile], '/api/v1/lots/batches')).not.toThrow()
  })
})
