import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient } from '@/api'
import type { ApiClient } from '@/api/types'
import {
  ApiError,
  type AvailableFilters,
  type InProgressSummary,
  type LotBulkDeleteResponse,
  type LotDetailResponse,
  type LotLifecycleFilter,
  type LotListQueryParams,
  type LotSortBy,
  type LotSortOrder,
  type LotSummary,
  type PaginationMeta,
  type RecalculateRequest,
  type RecalculateResponse,
  type TrafficLightColor,
} from '@/types/api'

const DEFAULT_PAGE_SIZE = 20
const BULK_DELETE_CHUNK_SIZE = 100

function cloneLotDetail(detail: LotDetailResponse): LotDetailResponse {
  return JSON.parse(JSON.stringify(detail)) as LotDetailResponse
}

function createEmptyInProgress(): InProgressSummary {
  return {
    active_batches_count: 0,
    total_processing_lots: 0,
    items: [],
  }
}

function createEmptyPagination(): PaginationMeta {
  return {
    total_items: 0,
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    total_pages: 0,
  }
}

function createEmptyFilters(): AvailableFilters {
  return {
    total_lots_count: 0,
    archived_lots_count: 0,
    makes: [],
    models: [],
    counts_by_verdict: {},
  }
}

export const useLotsStore = defineStore('lots', () => {
  const items = ref<LotSummary[]>([])
  const inProgress = ref<InProgressSummary>(createEmptyInProgress())
  const pagination = ref<PaginationMeta>(createEmptyPagination())
  const availableFilters = ref<AvailableFilters>(createEmptyFilters())

  const query = ref('')
  const selectedMake = ref<string | null>(null)
  const selectedModel = ref<string | null>(null)
  const selectedVerdict = ref<TrafficLightColor | null>(null)
  const onlyAnomalies = ref(false)
  const lifecycle = ref<LotLifecycleFilter>('active')
  const sortBy = ref<LotSortBy>('created_at')
  const sortOrder = ref<LotSortOrder>('desc')

  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const hasLoadedOnce = ref(false)
  const errorMessage = ref<string | null>(null)

  const baselineLotDetailsById = ref<Record<string, LotDetailResponse>>({})
  const currentLotDetail = ref<LotDetailResponse | null>(null)
  const isLoadingDetail = ref(false)
  const detailError = ref<string | null>(null)
  const detailErrorStatus = ref<number | null>(null)
  const isRecalculating = ref(false)
  const recalculateError = ref<string | null>(null)

  // Monotonic sequence guard ensures stale responses never overwrite newer filter results.
  let latestRequestId = 0
  let activeLoadingId = 0
  let activeLoadingMoreId = 0
  let latestPreviewRequestId = 0
  let latestDetailRequestId = 0
  let latestRecalcRequestId = 0

  const isSimulationModified = computed(() => {
    const current = currentLotDetail.value
    if (!current) return false
    if (typeof current.economics.is_simulation_modified === 'boolean') {
      return current.economics.is_simulation_modified
    }
    const baseline = baselineLotDetailsById.value[current.lot_id]
    if (!baseline) return false

    return (
      current.economics.wise_cost_ladder.car_bid_jpy !==
        baseline.economics.wise_cost_ladder.car_bid_jpy ||
      current.economics.customs.is_commercial_util !==
        baseline.economics.customs.is_commercial_util ||
      current.economics.is_repairs_included !== baseline.economics.is_repairs_included
    )
  })

  const activeFiltersCount = computed(() => {
    let count = 0
    if (selectedMake.value) count += 1
    if (selectedModel.value) count += 1
    if (selectedVerdict.value) count += 1
    if (onlyAnomalies.value) count += 1
    if (lifecycle.value !== 'active') count += 1
    if (sortBy.value !== 'created_at' || sortOrder.value !== 'desc') count += 1
    return count
  })

  const hasAnyActiveFilter = computed(() => {
    return query.value.trim().length > 0 || activeFiltersCount.value > 0
  })

  const hasMore = computed(() => {
    return pagination.value.page < pagination.value.total_pages
  })

  function buildQueryParams(page: number): LotListQueryParams {
    return {
      query: query.value.trim() || undefined,
      make: selectedMake.value || undefined,
      model: selectedModel.value || undefined,
      verdict: selectedVerdict.value || undefined,
      has_anomaly: onlyAnomalies.value ? true : undefined,
      lifecycle: lifecycle.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      page,
      page_size: DEFAULT_PAGE_SIZE,
    }
  }

  async function runFetchLots(silent: boolean, client: ApiClient): Promise<void> {
    const requestId = ++latestRequestId
    const loadingId = silent ? activeLoadingId : ++activeLoadingId
    if (!silent) {
      isLoading.value = true
      errorMessage.value = null
    }

    try {
      const response = await client.lots.list(buildQueryParams(1))
      if (requestId !== latestRequestId) return

      items.value = response.items
      inProgress.value = response.in_progress
      pagination.value = response.pagination
      availableFilters.value = response.available_filters
      hasLoadedOnce.value = true
    } catch (error: unknown) {
      if (requestId !== latestRequestId) return
      if (!silent) {
        errorMessage.value =
          error instanceof ApiError
            ? error.detail
            : error instanceof Error
              ? error.message
              : 'Не удалось загрузить список лотов.'
      }
    } finally {
      if (!silent && loadingId === activeLoadingId) {
        isLoading.value = false
      }
    }
  }

  async function fetchLots(client: ApiClient = apiClient): Promise<void> {
    return runFetchLots(false, client)
  }

  async function refreshLotsSilently(client: ApiClient = apiClient): Promise<void> {
    return runFetchLots(true, client)
  }

  async function loadMore(client: ApiClient = apiClient): Promise<void> {
    if (isLoading.value || isLoadingMore.value || !hasMore.value) {
      return
    }

    const requestId = ++latestRequestId
    const loadingMoreId = ++activeLoadingMoreId
    const nextPage = pagination.value.page + 1
    isLoadingMore.value = true
    errorMessage.value = null

    try {
      const response = await client.lots.list(buildQueryParams(nextPage))
      if (requestId !== latestRequestId) return

      const seenIds = new Set(items.value.map((item) => item.lot_id))
      const appended = response.items.filter((item) => !seenIds.has(item.lot_id))
      items.value = [...items.value, ...appended]
      inProgress.value = response.in_progress
      pagination.value = response.pagination
      availableFilters.value = response.available_filters
    } catch (error: unknown) {
      if (requestId !== latestRequestId) return
      errorMessage.value =
        error instanceof ApiError
          ? error.detail
          : error instanceof Error
            ? error.message
            : 'Не удалось загрузить следующую страницу лотов.'
    } finally {
      if (loadingMoreId === activeLoadingMoreId) {
        isLoadingMore.value = false
      }
    }
  }

  async function fetchFilterPreview(
    overrides: Partial<LotListQueryParams>,
    client: ApiClient = apiClient,
  ): Promise<AvailableFilters | null> {
    const previewId = ++latestPreviewRequestId

    try {
      const response = await client.lots.list({
        lifecycle: lifecycle.value,
        ...overrides,
        page: 1,
        page_size: 1,
      })
      if (previewId !== latestPreviewRequestId) return null
      return response.available_filters
    } catch {
      return null
    }
  }

  async function fetchLotDetail(
    lotId: string,
    client: ApiClient = apiClient,
  ): Promise<LotDetailResponse | null> {
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
      const response = await client.lots.getDetail(lotId)
      if (requestId !== latestDetailRequestId) return null

      baselineLotDetailsById.value[lotId] = cloneLotDetail(response)
      currentLotDetail.value = response
      return response
    } catch (error: unknown) {
      if (requestId !== latestDetailRequestId) return null
      detailErrorStatus.value = error instanceof ApiError ? error.status : 0
      detailError.value =
        error instanceof ApiError
          ? error.detail
          : error instanceof Error
            ? error.message
            : 'Не удалось загрузить спецификацию лота.'
      return null
    } finally {
      if (requestId === latestDetailRequestId) {
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
      const updatedDetail: LotDetailResponse = {
        ...currentLotDetail.value,
        updated_at: response.recalculated_at,
        verdict: response.verdict,
        economics: {
          ...currentLotDetail.value.economics,
          is_repairs_included: response.include_repairs,
          is_simulation_modified: options.resetBaseline ? false : response.is_simulation_modified,
          customs: response.customs,
          wise_cost_ladder: response.wise_cost_ladder,
        },
      }
      currentLotDetail.value = updatedDetail
      if (options.resetBaseline) {
        baselineLotDetailsById.value[lotId] = cloneLotDetail(updatedDetail)
      }
    }

    items.value = items.value.map((item) =>
      item.lot_id === lotId
        ? {
            ...item,
            turnkey_cost_rub: response.turnkey_cost_rub,
            net_benefit_rub: response.net_benefit_rub,
            verdict: response.verdict.verdict,
            verdict_headline: response.verdict.short_verdict_label,
          }
        : item,
    )
  }

  async function runEconomicsMutation(
    lotId: string,
    execute: () => Promise<RecalculateResponse>,
    fallbackError: string,
    options: { resetBaseline: boolean },
  ): Promise<RecalculateResponse | null> {
    const requestId = ++latestRecalcRequestId
    isRecalculating.value = true
    recalculateError.value = null

    try {
      const response = await execute()
      if (requestId !== latestRecalcRequestId || currentLotDetail.value?.lot_id !== lotId) {
        return null
      }
      applyRecalculateToState(lotId, response, options)
      return response
    } catch (error: unknown) {
      if (requestId !== latestRecalcRequestId || currentLotDetail.value?.lot_id !== lotId) {
        return null
      }
      recalculateError.value =
        error instanceof ApiError
          ? error.detail
          : error instanceof Error
            ? error.message
            : fallbackError
      return null
    } finally {
      if (requestId === latestRecalcRequestId) {
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

  async function setLotArchived(
    lotId: string,
    isArchived: boolean,
    client: ApiClient = apiClient,
  ): Promise<LotSummary> {
    const updated = await client.lots.updateLifecycle(lotId, { is_archived: isArchived })

    const updatedCurrent = applyLifecycleToDetail(
      currentLotDetail.value?.lot_id === lotId ? currentLotDetail.value : undefined,
      updated,
    )
    if (updatedCurrent) {
      currentLotDetail.value = updatedCurrent
    }

    const updatedBaseline = applyLifecycleToDetail(baselineLotDetailsById.value[lotId], updated)
    if (updatedBaseline) {
      baselineLotDetailsById.value[lotId] = updatedBaseline
    }

    const matchesCurrentScope =
      lifecycle.value === 'all' ||
      (lifecycle.value === 'active' && !updated.is_archived) ||
      (lifecycle.value === 'archived' && updated.is_archived)

    if (matchesCurrentScope) {
      items.value = items.value.map((item) => (item.lot_id === lotId ? updated : item))
    } else {
      items.value = items.value.filter((item) => item.lot_id !== lotId)
    }

    if (hasLoadedOnce.value) {
      await refreshLotsSilently(client)
    }

    return updated
  }

  function removeLotsLocally(lotIds: ReadonlySet<string>): void {
    items.value = items.value.filter((item) => !lotIds.has(item.lot_id))
    for (const id of lotIds) {
      delete baselineLotDetailsById.value[id]
    }
    if (currentLotDetail.value && lotIds.has(currentLotDetail.value.lot_id)) {
      currentLotDetail.value = null
    }
  }

  async function deleteLot(lotId: string, client: ApiClient = apiClient): Promise<void> {
    await client.lots.deleteLot(lotId)
    removeLotsLocally(new Set([lotId]))
    if (hasLoadedOnce.value) {
      await refreshLotsSilently(client)
    }
  }

  async function bulkDeleteLots(
    lotIds: readonly string[],
    client: ApiClient = apiClient,
  ): Promise<LotBulkDeleteResponse> {
    const uniqueIds = Array.from(new Set(lotIds))
    if (uniqueIds.length === 0) {
      return { deleted_ids: [], not_found_ids: [], deleted_count: 0 }
    }

    const deletedIds: string[] = []
    const notFoundIds: string[] = []

    for (let offset = 0; offset < uniqueIds.length; offset += BULK_DELETE_CHUNK_SIZE) {
      const chunk = uniqueIds.slice(offset, offset + BULK_DELETE_CHUNK_SIZE)
      const res = await client.lots.bulkDeleteLots({ lot_ids: chunk })
      deletedIds.push(...res.deleted_ids)
      notFoundIds.push(...res.not_found_ids)
    }

    removeLotsLocally(new Set([...deletedIds, ...notFoundIds]))
    if (hasLoadedOnce.value) {
      await refreshLotsSilently(client)
    }

    return {
      deleted_ids: deletedIds,
      not_found_ids: notFoundIds,
      deleted_count: deletedIds.length,
    }
  }

  function resetFilters(): void {
    query.value = ''
    selectedMake.value = null
    selectedModel.value = null
    selectedVerdict.value = null
    onlyAnomalies.value = false
    lifecycle.value = 'active'
    sortBy.value = 'created_at'
    sortOrder.value = 'desc'
  }

  function clear(): void {
    latestRequestId += 1
    activeLoadingId += 1
    activeLoadingMoreId += 1
    latestPreviewRequestId += 1
    latestDetailRequestId += 1
    latestRecalcRequestId += 1
    items.value = []
    inProgress.value = createEmptyInProgress()
    pagination.value = createEmptyPagination()
    availableFilters.value = createEmptyFilters()
    isLoading.value = false
    isLoadingMore.value = false
    hasLoadedOnce.value = false
    errorMessage.value = null
    baselineLotDetailsById.value = {}
    currentLotDetail.value = null
    isLoadingDetail.value = false
    detailError.value = null
    detailErrorStatus.value = null
    isRecalculating.value = false
    recalculateError.value = null
    resetFilters()
  }

  return {
    items,
    inProgress,
    pagination,
    availableFilters,
    query,
    selectedMake,
    selectedModel,
    selectedVerdict,
    onlyAnomalies,
    lifecycle,
    sortBy,
    sortOrder,
    isLoading,
    isLoadingMore,
    hasLoadedOnce,
    errorMessage,
    currentLotDetail,
    isLoadingDetail,
    detailError,
    detailErrorStatus,
    isRecalculating,
    recalculateError,
    isSimulationModified,
    activeFiltersCount,
    hasAnyActiveFilter,
    hasMore,
    fetchLots,
    refreshLotsSilently,
    loadMore,
    fetchFilterPreview,
    fetchLotDetail,
    recalculateLot,
    resetLotSimulation,
    setLotArchived,
    deleteLot,
    bulkDeleteLots,
    resetFilters,
    clear,
  }
})
