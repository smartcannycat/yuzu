import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient } from '@/api'
import { isAbortError } from '@/api/http/transport'
import type { ApiClient } from '@/api/types'
import {
  applyLifecycleScopeFilter,
  applyLotSummaryEconomics,
  buildLotQueryParams,
  countActiveLotFilters,
  createEmptyFilters,
  createEmptyInProgress,
  createEmptyPagination,
  executeChunkedBulkDelete,
  fetchLoadedPagesWindow,
} from '@/stores/lotFeedHelpers'
import type {
  AvailableFilters,
  InProgressSummary,
  LotBulkDeleteResponse,
  LotLifecycleFilter,
  LotListQueryParams,
  LotSortBy,
  LotSortOrder,
  LotSummary,
  PaginationMeta,
  RecalculateResponse,
  TrafficLightColor,
} from '@/types/api'
import { extractApiErrorMessage } from '@/utils/errors'
import { emitLotLifecycleUpdated, emitLotsRemoved, onSessionReset } from '@/utils/sessionEvents'

export const useLotFeedStore = defineStore('lotFeed', () => {
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

  let latestRequestId = 0
  let activeLoadingId = 0
  let activeLoadingMoreId = 0
  let latestPreviewRequestId = 0
  let sessionEpoch = 0
  let feedAbortController: AbortController | null = null

  const activeFiltersCount = computed(() =>
    countActiveLotFilters({
      selectedMake: selectedMake.value,
      selectedModel: selectedModel.value,
      selectedVerdict: selectedVerdict.value,
      onlyAnomalies: onlyAnomalies.value,
      lifecycle: lifecycle.value,
      sortBy: sortBy.value,
      sortOrder: sortOrder.value,
    }),
  )

  const hasAnyActiveFilter = computed(
    () => query.value.trim().length > 0 || activeFiltersCount.value > 0,
  )

  const hasMore = computed(() => pagination.value.page < pagination.value.total_pages)

  function buildQueryParams(page: number): LotListQueryParams {
    return buildLotQueryParams(
      {
        query: query.value,
        selectedMake: selectedMake.value,
        selectedModel: selectedModel.value,
        selectedVerdict: selectedVerdict.value,
        onlyAnomalies: onlyAnomalies.value,
        lifecycle: lifecycle.value,
        sortBy: sortBy.value,
        sortOrder: sortOrder.value,
      },
      page,
    )
  }

  async function fetchLots(client: ApiClient = apiClient): Promise<void> {
    feedAbortController?.abort()
    const controller = new AbortController()
    feedAbortController = controller

    const epoch = sessionEpoch
    const requestId = ++latestRequestId
    const loadingId = ++activeLoadingId
    isLoading.value = true
    errorMessage.value = null

    try {
      const response = await client.lots.list(buildQueryParams(1), { signal: controller.signal })
      if (epoch !== sessionEpoch || requestId !== latestRequestId) return

      items.value = response.items
      inProgress.value = response.in_progress
      pagination.value = response.pagination
      availableFilters.value = response.available_filters
      hasLoadedOnce.value = true
    } catch (error: unknown) {
      if (isAbortError(error) || epoch !== sessionEpoch || requestId !== latestRequestId) return
      errorMessage.value = extractApiErrorMessage(error, 'Не удалось загрузить список лотов.')
    } finally {
      if (feedAbortController === controller) {
        feedAbortController = null
      }
      if (epoch === sessionEpoch && loadingId === activeLoadingId) {
        isLoading.value = false
      }
    }
  }

  async function refreshLotsSilently(client: ApiClient = apiClient): Promise<void> {
    feedAbortController?.abort()
    const controller = new AbortController()
    feedAbortController = controller

    const epoch = sessionEpoch
    const requestId = ++latestRequestId
    const loadedPageCount = Math.max(1, pagination.value.page)

    try {
      const { items: refreshedItems, metaSource } = await fetchLoadedPagesWindow(
        client,
        buildQueryParams,
        loadedPageCount,
        controller.signal,
      )
      if (epoch !== sessionEpoch || requestId !== latestRequestId) return

      items.value = refreshedItems
      inProgress.value = metaSource.in_progress
      pagination.value = metaSource.pagination
      availableFilters.value = metaSource.available_filters
      hasLoadedOnce.value = true
    } catch {
      // Background refreshes never overwrite visible feed items with error states.
    } finally {
      if (feedAbortController === controller) {
        feedAbortController = null
      }
    }
  }

  async function loadMore(client: ApiClient = apiClient): Promise<void> {
    if (isLoading.value || isLoadingMore.value || !hasMore.value) return

    const epoch = sessionEpoch
    const requestId = ++latestRequestId
    const loadingMoreId = ++activeLoadingMoreId
    isLoadingMore.value = true
    errorMessage.value = null

    try {
      const response = await client.lots.list(buildQueryParams(pagination.value.page + 1))
      if (epoch !== sessionEpoch || requestId !== latestRequestId) return

      const seenIds = new Set(items.value.map((item) => item.lot_id))
      const appended = response.items.filter((item) => !seenIds.has(item.lot_id))
      items.value = [...items.value, ...appended]
      inProgress.value = response.in_progress
      pagination.value = response.pagination
      availableFilters.value = response.available_filters
    } catch (error: unknown) {
      if (isAbortError(error) || epoch !== sessionEpoch || requestId !== latestRequestId) return
      errorMessage.value = extractApiErrorMessage(
        error,
        'Не удалось загрузить следующую страницу лотов.',
      )
    } finally {
      if (epoch === sessionEpoch && loadingMoreId === activeLoadingMoreId) {
        isLoadingMore.value = false
      }
    }
  }

  async function fetchFilterPreview(
    overrides: Partial<LotListQueryParams>,
    client: ApiClient = apiClient,
  ): Promise<AvailableFilters | null> {
    const epoch = sessionEpoch
    const previewId = ++latestPreviewRequestId

    try {
      const response = await client.lots.list({
        lifecycle: lifecycle.value,
        ...overrides,
        page: 1,
        page_size: 1,
      })
      if (epoch !== sessionEpoch || previewId !== latestPreviewRequestId) return null
      return response.available_filters
    } catch {
      return null
    }
  }

  function applyLotEconomicsUpdate(lotId: string, response: RecalculateResponse): void {
    items.value = applyLotSummaryEconomics(items.value, lotId, response)
  }

  function removeLotsLocally(lotIds: ReadonlySet<string>): void {
    if (lotIds.size === 0) return
    items.value = items.value.filter((item) => !lotIds.has(item.lot_id))
    emitLotsRemoved(lotIds)
  }

  async function setLotArchived(
    lotId: string,
    isArchived: boolean,
    client: ApiClient = apiClient,
  ): Promise<LotSummary> {
    const epoch = sessionEpoch
    const updated = await client.lots.updateLifecycle(lotId, { is_archived: isArchived })
    if (epoch !== sessionEpoch) return updated

    items.value = applyLifecycleScopeFilter(items.value, updated, lifecycle.value)
    emitLotLifecycleUpdated(updated)
    if (hasLoadedOnce.value) {
      await refreshLotsSilently(client)
    }
    return updated
  }

  async function deleteLot(lotId: string, client: ApiClient = apiClient): Promise<void> {
    const epoch = sessionEpoch
    await client.lots.deleteLot(lotId)
    if (epoch !== sessionEpoch) return

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

    const epoch = sessionEpoch
    const result = await executeChunkedBulkDelete(
      client,
      uniqueIds,
      () => epoch !== sessionEpoch,
      removeLotsLocally,
    )
    if (hasLoadedOnce.value && epoch === sessionEpoch) {
      await refreshLotsSilently(client)
    }
    return result
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
    sessionEpoch += 1
    latestRequestId += 1
    activeLoadingId += 1
    activeLoadingMoreId += 1
    latestPreviewRequestId += 1
    feedAbortController?.abort()
    feedAbortController = null
    items.value = []
    inProgress.value = createEmptyInProgress()
    pagination.value = createEmptyPagination()
    availableFilters.value = createEmptyFilters()
    isLoading.value = false
    isLoadingMore.value = false
    hasLoadedOnce.value = false
    errorMessage.value = null
    resetFilters()
  }

  onSessionReset('lotFeed', clear)

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
    activeFiltersCount,
    hasAnyActiveFilter,
    hasMore,
    fetchLots,
    refreshLotsSilently,
    loadMore,
    fetchFilterPreview,
    applyLotEconomicsUpdate,
    setLotArchived,
    deleteLot,
    bulkDeleteLots,
    resetFilters,
    clear,
  }
})
