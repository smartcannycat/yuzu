import { delay } from '@/api/mock/helpers'
import { buildMockLotDetail, recalculateMockLotDetail } from '@/api/mock/lotDetails'
import { queryMockLots } from '@/api/mock/lotFilters'
import { createMockLotsWorkspace, type MockLotsWorkspace } from '@/api/mock/lotsBatches'
import type { LotsApi } from '@/api/types'
import {
  ApiError,
  type BatchCreateResponse,
  type BatchProgressResponse,
  type LotBulkDeleteRequest,
  type LotBulkDeleteResponse,
  type LotDetailResponse,
  type LotLifecyclePatchRequest,
  type LotListQueryParams,
  type LotListResponse,
  type LotSummary,
  type RecalculateRequest,
  type RecalculateResponse,
} from '@/types/api'

export { queryMockLots }

export function applyRecalculateToDetail(
  current: LotDetailResponse,
  response: RecalculateResponse,
): LotDetailResponse {
  return {
    ...current,
    updated_at: response.recalculated_at,
    passport: {
      ...current.passport,
      ...(response.power_hp !== undefined ? { power_hp: response.power_hp } : {}),
      ...(response.power_hp_source !== undefined
        ? { power_hp_source: response.power_hp_source }
        : {}),
      ...(response.is_under_160_hp !== undefined
        ? { is_under_160_hp: response.is_under_160_hp }
        : {}),
      ...(response.ocr_warnings !== undefined ? { ocr_warnings: response.ocr_warnings } : {}),
    },
    verdict: response.verdict,
    economics: {
      ...current.economics,
      ...(response.bid_slider_min_jpy !== undefined
        ? { bid_slider_min_jpy: response.bid_slider_min_jpy }
        : {}),
      is_repairs_included: response.include_repairs,
      is_simulation_modified: response.is_simulation_modified ?? false,
      customs: response.customs,
      wise_cost_ladder: response.wise_cost_ladder,
    },
  }
}

export function persistMockDetail(
  current: LotDetailResponse,
  response: RecalculateResponse,
  detailCache: Map<string, LotDetailResponse>,
  workspace: MockLotsWorkspace,
): LotDetailResponse {
  const updated = applyRecalculateToDetail(current, response)
  detailCache.set(current.lot_id, updated)
  workspace.updateLotEconomics(current.lot_id, response)
  return updated
}

function syncDetailLifecycle(detail: LotDetailResponse, summary: LotSummary): LotDetailResponse {
  return {
    ...detail,
    is_archived: summary.is_archived,
    archived_at: summary.archived_at,
    archived_reason: summary.archived_reason,
    expires_at: summary.expires_at,
    passport: {
      ...detail.passport,
      auction_date: summary.auction_date,
    },
  }
}

function isModifiedAgainstBaseline(
  baseline: LotDetailResponse,
  response: RecalculateResponse,
): boolean {
  return (
    response.applied_bid_jpy !== baseline.economics.wise_cost_ladder.car_bid_jpy ||
    response.is_commercial_util !== baseline.economics.customs.is_commercial_util ||
    response.include_repairs !== baseline.economics.is_repairs_included ||
    response.customs.freight_vladivostok_rub !==
      baseline.economics.customs.freight_vladivostok_rub ||
    (response.power_hp !== undefined && response.power_hp !== baseline.passport.power_hp)
  )
}

export function createMockLotsApi(defaultDelay: number, persistState = false): LotsApi {
  const workspace = createMockLotsWorkspace({ persistState })
  const detailCache = new Map<string, LotDetailResponse>()
  const baselineCache = new Map<string, LotDetailResponse>()

  function resolveLotDetail(lotId: string): LotDetailResponse {
    const snapshot = workspace.getFeedSnapshot()
    const summary = snapshot.lots.find((item) => item.lot_id === lotId)
    if (!summary) {
      detailCache.delete(lotId)
      throw new ApiError({
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        detail: 'Лот не найден.',
      })
    }

    const cached = detailCache.get(lotId)
    if (cached) {
      const synced = syncDetailLifecycle(cached, summary)
      detailCache.set(lotId, synced)
      return synced
    }

    const detail = buildMockLotDetail(summary)
    baselineCache.set(lotId, structuredClone(detail))
    detailCache.set(lotId, detail)
    return detail
  }

  return {
    async list(params?: LotListQueryParams): Promise<LotListResponse> {
      await delay(Math.min(defaultDelay, 160))
      const snapshot = workspace.getFeedSnapshot()
      return queryMockLots(params, snapshot.lots, snapshot.inProgress)
    },

    async getDetail(lotId: string): Promise<LotDetailResponse> {
      await delay(Math.min(defaultDelay, 160))
      return resolveLotDetail(lotId)
    },

    async recalculate(lotId: string, payload: RecalculateRequest): Promise<RecalculateResponse> {
      await delay(Math.min(defaultDelay, 120))
      const current = resolveLotDetail(lotId)
      const baseline = baselineCache.get(lotId) ?? current
      const raw = recalculateMockLotDetail(current, payload)
      const response: RecalculateResponse = {
        ...raw,
        is_simulation_modified: isModifiedAgainstBaseline(baseline, raw),
      }
      persistMockDetail(current, response, detailCache, workspace)
      return response
    },

    async resetSimulation(lotId: string): Promise<RecalculateResponse> {
      await delay(Math.min(defaultDelay, 120))
      const current = resolveLotDetail(lotId)
      const baseline = structuredClone(baselineCache.get(lotId) ?? current)
      detailCache.set(lotId, structuredClone(baseline))
      const ladder = baseline.economics.wise_cost_ladder
      const response: RecalculateResponse = {
        lot_id: baseline.lot_id,
        recalculated_at: new Date().toISOString(),
        applied_bid_jpy: ladder.car_bid_jpy,
        applied_bid_rub: ladder.car_bid_rub,
        is_commercial_util: baseline.economics.customs.is_commercial_util,
        include_repairs: baseline.economics.is_repairs_included,
        customs: baseline.economics.customs,
        wise_cost_ladder: ladder,
        turnkey_cost_rub: ladder.turnkey_cost_rub,
        market_price_rf_rub: ladder.market_price_rf_rub,
        net_benefit_rub: ladder.net_benefit_rub,
        benefit_percentage: ladder.benefit_percentage,
        power_hp: baseline.passport.power_hp,
        power_hp_source: baseline.passport.power_hp_source,
        is_under_160_hp: baseline.passport.is_under_160_hp,
        ocr_warnings: baseline.passport.ocr_warnings,
        verdict: baseline.verdict,
        is_simulation_modified: false,
        pdf_report_stale: false,
      }
      workspace.updateLotEconomics(lotId, response)
      return response
    },

    async updateLifecycle(lotId: string, payload: LotLifecyclePatchRequest): Promise<LotSummary> {
      await delay(Math.min(defaultDelay, 120))
      const updated = workspace.updateLotLifecycle(lotId, payload.is_archived)
      const cached = detailCache.get(lotId)
      if (cached) {
        detailCache.set(lotId, {
          ...syncDetailLifecycle(cached, updated),
          updated_at: updated.archived_at ?? new Date().toISOString(),
        })
      }
      return updated
    },

    async deleteLot(lotId: string): Promise<void> {
      await delay(Math.min(defaultDelay, 120))
      workspace.deleteLot(lotId)
      detailCache.delete(lotId)
      baselineCache.delete(lotId)
    },

    async bulkDeleteLots(payload: LotBulkDeleteRequest): Promise<LotBulkDeleteResponse> {
      await delay(Math.min(defaultDelay, 160))
      const result = workspace.bulkDeleteLots(payload.lot_ids)
      for (const deletedId of result.deleted_ids) {
        detailCache.delete(deletedId)
        baselineCache.delete(deletedId)
      }
      return result
    },

    async createBatch(files: readonly File[]): Promise<BatchCreateResponse> {
      await delay(Math.min(defaultDelay, 220))
      return workspace.createBatch(files)
    },

    async getBatch(batchId: string): Promise<BatchProgressResponse> {
      await delay(Math.min(defaultDelay, 120))
      return workspace.getBatch(batchId)
    },

    async appendBatchItems(
      batchId: string,
      files: readonly File[],
    ): Promise<BatchProgressResponse> {
      await delay(Math.min(defaultDelay, 180))
      return workspace.appendBatchItems(batchId, files)
    },
  }
}
