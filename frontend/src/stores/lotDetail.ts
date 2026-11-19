import { defineStore } from 'pinia'
import { computed, ref, shallowRef, toRaw } from 'vue'

import { apiClient } from '@/api'
import { isAbortError } from '@/api/http/transport'
import type { ApiClient } from '@/api/types'
import { useLotFeedStore } from '@/stores/lotFeed'
import {
  ApiError,
  type LotDetailResponse,
  type LotSummary,
  type RecalculateRequest,
  type RecalculateResponse,
} from '@/types/api'
import { extractApiErrorMessage } from '@/utils/errors'
import { onLotLifecycleUpdated, onLotsRemoved, onSessionReset } from '@/utils/sessionEvents'

const MAX_BASELINE_CACHE_ENTRIES = 20

function unwrapReactive<T>(value: T): T {
  const raw = toRaw(value)
  if (Array.isArray(raw)) {
    return raw.map((item) => unwrapReactive(item)) as T
  }
  if (raw !== null && typeof raw === 'object') {
    const out: Record<string, unknown> = {}
    for (const [key, entry] of Object.entries(raw)) {
      out[key] = unwrapReactive(entry)
    }
    return out as T
  }
  return raw
}

function cloneLotDetail(detail: LotDetailResponse): LotDetailResponse {
  return structuredClone(unwrapReactive(detail))
}

function applyLifecycleToDetail(
  detail: LotDetailResponse | undefined,
  updated: LotSummary,
): LotDetailResponse | undefined {
  if (!detail) return undefined
  return {
    ...detail,
    is_archived: updated.is_archived,
    archived_at: updated.archived_at,
    archived_reason: updated.archived_reason,
    expires_at: updated.expires_at,
  }
}

export const useLotDetailStore = defineStore('lotDetail', () => {
  const baselineLotDetailsById = shallowRef<Map<string, LotDetailResponse>>(new Map())
  const currentLotDetail = ref<LotDetailResponse | null>(null)
  const isLoadingDetail = ref(false)
  const detailError = ref<string | null>(null)
  const detailErrorStatus = ref<number | null>(null)
  const isRecalculating = ref(false)
  const recalculateError = ref<string | null>(null)

  let latestDetailRequestId = 0
  let latestRecalcRequestId = 0
  let sessionEpoch = 0
  let detailAbortController: AbortController | null = null

  function setBaselineEntry(lotId: string, detail: LotDetailResponse): void {
    const next = new Map(baselineLotDetailsById.value)
    next.delete(lotId)
    next.set(lotId, cloneLotDetail(detail))
    while (next.size > MAX_BASELINE_CACHE_ENTRIES) {
      const oldestKey = next.keys().next().value
      if (oldestKey === undefined) break
      next.delete(oldestKey)
    }
    baselineLotDetailsById.value = next
  }

  function removeLotsFromDetailCache(lotIds: ReadonlySet<string>): void {
    if (lotIds.size === 0) return
    const next = new Map(baselineLotDetailsById.value)
    let changed = false
    for (const id of lotIds) {
      if (next.delete(id)) {
        changed = true
      }
    }
    if (changed) {
      baselineLotDetailsById.value = next
    }
    if (currentLotDetail.value && lotIds.has(currentLotDetail.value.lot_id)) {
      currentLotDetail.value = null
    }
  }

  function applyLifecycleUpdate(updated: LotSummary): void {
    if (currentLotDetail.value?.lot_id === updated.lot_id) {
      const nextCurrent = applyLifecycleToDetail(currentLotDetail.value, updated)
      if (nextCurrent) {
        currentLotDetail.value = nextCurrent
      }
    }
    const existingBaseline = baselineLotDetailsById.value.get(updated.lot_id)
    const nextBaseline = applyLifecycleToDetail(existingBaseline, updated)
    if (nextBaseline) {
      setBaselineEntry(updated.lot_id, nextBaseline)
    }
  }

  const isSimulationModified = computed(() => {
    const current = currentLotDetail.value
    if (!current) return false
    if (typeof current.economics.is_simulation_modified === 'boolean') {
      return current.economics.is_simulation_modified
    }
    const baseline = baselineLotDetailsById.value.get(current.lot_id)
    if (!baseline) return false

    return (
      current.economics.wise_cost_ladder.car_bid_jpy !==
        baseline.economics.wise_cost_ladder.car_bid_jpy ||
      current.economics.customs.is_commercial_util !==
        baseline.economics.customs.is_commercial_util ||
      current.economics.is_repairs_included !== baseline.economics.is_repairs_included
    )
  })

  async function fetchLotDetail(
    lotId: string,
    client: ApiClient = apiClient,
  ): Promise<LotDetailResponse | null> {
    detailAbortController?.abort()
    const controller = new AbortController()
    detailAbortController = controller

    const epoch = sessionEpoch
    const requestId = ++latestDetailRequestId
    latestRecalcRequestId += 1
    isRecalculating.value = false
    isLoadingDetail.value = true
    detailError.value = null
    detailErrorStatus.value = null
    recalculateError.value = null

    if (currentLotDetail.value?.lot_id !== lotId) {
      currentLotDetail.value = null
    }

    try {
      const response = await client.lots.getDetail(lotId, { signal: controller.signal })
      if (epoch !== sessionEpoch || requestId !== latestDetailRequestId) return null

      setBaselineEntry(lotId, response)
      currentLotDetail.value = response
      return response
    } catch (error: unknown) {
      if (isAbortError(error) || epoch !== sessionEpoch || requestId !== latestDetailRequestId) {
        return null
      }
      detailErrorStatus.value = error instanceof ApiError ? error.status : 0
      detailError.value = extractApiErrorMessage(error, 'Не удалось загрузить спецификацию лота.')
      return null
    } finally {
      if (detailAbortController === controller) {
        detailAbortController = null
      }
      if (epoch === sessionEpoch && requestId === latestDetailRequestId) {
        isLoadingDetail.value = false
      }
    }
  }

  function applyRecalculateToState(
    lotId: string,
    response: RecalculateResponse,
    options: { resetBaseline: boolean },
  ): void {
    if (currentLotDetail.value?.lot_id === lotId) {
      const current = currentLotDetail.value
      const updatedDetail: LotDetailResponse = {
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
          is_simulation_modified: options.resetBaseline ? false : response.is_simulation_modified,
          customs: response.customs,
          wise_cost_ladder: response.wise_cost_ladder,
        },
      }
      currentLotDetail.value = updatedDetail
      if (options.resetBaseline) {
        setBaselineEntry(lotId, updatedDetail)
      }
    }

    useLotFeedStore().applyLotEconomicsUpdate(lotId, response)
  }

  async function runEconomicsMutation(
    lotId: string,
    execute: () => Promise<RecalculateResponse>,
    fallbackError: string,
    options: { resetBaseline: boolean },
  ): Promise<RecalculateResponse | null> {
    const epoch = sessionEpoch
    const requestId = ++latestRecalcRequestId
    isRecalculating.value = true
    recalculateError.value = null

    try {
      const response = await execute()
      if (
        epoch !== sessionEpoch ||
        requestId !== latestRecalcRequestId ||
        currentLotDetail.value?.lot_id !== lotId
      ) {
        return null
      }
      applyRecalculateToState(lotId, response, options)
      return response
    } catch (error: unknown) {
      if (
        epoch !== sessionEpoch ||
        requestId !== latestRecalcRequestId ||
        currentLotDetail.value?.lot_id !== lotId
      ) {
        return null
      }
      recalculateError.value = extractApiErrorMessage(error, fallbackError)
      return null
    } finally {
      if (epoch === sessionEpoch && requestId === latestRecalcRequestId) {
        isRecalculating.value = false
      }
    }
  }

  async function recalculateLot(
    lotId: string,
    payload: RecalculateRequest,
    client: ApiClient = apiClient,
  ): Promise<RecalculateResponse | null> {
    return runEconomicsMutation(
      lotId,
      () => client.lots.recalculate(lotId, payload),
      'Не удалось пересчитать экономику лота.',
      { resetBaseline: false },
    )
  }

  async function resetLotSimulation(
    lotId: string,
    client: ApiClient = apiClient,
  ): Promise<RecalculateResponse | null> {
    return runEconomicsMutation(
      lotId,
      () => client.lots.resetSimulation(lotId),
      'Не удалось сбросить параметры симуляции.',
      { resetBaseline: true },
    )
  }

  async function setLotArchived(
    lotId: string,
    isArchived: boolean,
    client: ApiClient = apiClient,
  ): Promise<LotSummary> {
    const epoch = sessionEpoch
    const updated = await useLotFeedStore().setLotArchived(lotId, isArchived, client)
    if (epoch === sessionEpoch) {
      applyLifecycleUpdate(updated)
    }
    return updated
  }

  async function deleteLot(lotId: string, client: ApiClient = apiClient): Promise<void> {
    const epoch = sessionEpoch
    await useLotFeedStore().deleteLot(lotId, client)
    if (epoch === sessionEpoch) {
      removeLotsFromDetailCache(new Set([lotId]))
    }
  }

  function clear(): void {
    sessionEpoch += 1
    latestDetailRequestId += 1
    latestRecalcRequestId += 1
    detailAbortController?.abort()
    detailAbortController = null
    baselineLotDetailsById.value = new Map()
    currentLotDetail.value = null
    isLoadingDetail.value = false
    detailError.value = null
    detailErrorStatus.value = null
    isRecalculating.value = false
    recalculateError.value = null
  }

  onSessionReset('lotDetail', clear)
  onLotsRemoved('lotDetail', removeLotsFromDetailCache)
  onLotLifecycleUpdated('lotDetail', applyLifecycleUpdate)

  return {
    currentLotDetail,
    isLoadingDetail,
    detailError,
    detailErrorStatus,
    isRecalculating,
    recalculateError,
    isSimulationModified,
    fetchLotDetail,
    recalculateLot,
    resetLotSimulation,
    setLotArchived,
    deleteLot,
    clear,
  }
})
