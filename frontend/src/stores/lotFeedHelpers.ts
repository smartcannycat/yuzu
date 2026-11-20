import type { ApiClient } from '@/api/types'
import type {
  AvailableFilters,
  InProgressSummary,
  LotBulkDeleteResponse,
  LotLifecycleFilter,
  LotListQueryParams,
  LotListResponse,
  LotSortBy,
  LotSortOrder,
  LotSummary,
  PaginationMeta,
  RecalculateResponse,
  TrafficLightColor,
} from '@/types/api'

export const DEFAULT_PAGE_SIZE = 20
export const BULK_DELETE_CHUNK_SIZE = 100

export interface LotFeedFilterState {
  query: string
  selectedMake: string | null
  selectedModel: string | null
  selectedVerdict: TrafficLightColor | null
  onlyAnomalies: boolean
  lifecycle: LotLifecycleFilter
  sortBy: LotSortBy
  sortOrder: LotSortOrder
}

export function createEmptyInProgress(): InProgressSummary {
  return {
    active_batches_count: 0,
    total_processing_lots: 0,
    items: [],
  }
}

export function createEmptyPagination(): PaginationMeta {
  return {
    total_items: 0,
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    total_pages: 0,
  }
}

export function createEmptyFilters(): AvailableFilters {
  return {
    total_lots_count: 0,
    archived_lots_count: 0,
    makes: [],
    models: [],
    counts_by_verdict: {},
  }
}

export function countActiveLotFilters(state: Omit<LotFeedFilterState, 'query'>): number {
  let count = 0
  if (state.selectedMake) count += 1
  if (state.selectedModel) count += 1
  if (state.selectedVerdict) count += 1
  if (state.onlyAnomalies) count += 1
  if (state.lifecycle !== 'active') count += 1
  if (state.sortBy !== 'created_at' || state.sortOrder !== 'desc') count += 1
  return count
}

export function buildLotQueryParams(state: LotFeedFilterState, page: number): LotListQueryParams {
  return {
    query: state.query.trim() || undefined,
    make: state.selectedMake || undefined,
    model: state.selectedModel || undefined,
    verdict: state.selectedVerdict || undefined,
    has_anomaly: state.onlyAnomalies ? true : undefined,
    lifecycle: state.lifecycle,
    sort_by: state.sortBy,
    sort_order: state.sortOrder,
    page,
    page_size: DEFAULT_PAGE_SIZE,
  }
}

export function applyLifecycleScopeFilter(
  items: readonly LotSummary[],
  updated: LotSummary,
  lifecycle: LotLifecycleFilter,
): LotSummary[] {
  const matchesScope =
    lifecycle === 'all' ||
    (lifecycle === 'active' && !updated.is_archived) ||
    (lifecycle === 'archived' && updated.is_archived)

  return matchesScope
    ? items.map((item) => (item.lot_id === updated.lot_id ? updated : item))
    : items.filter((item) => item.lot_id !== updated.lot_id)
}

export function applyLotSummaryEconomics(
  items: readonly LotSummary[],
  lotId: string,
  response: RecalculateResponse,
): LotSummary[] {
  return items.map((item) =>
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

export function mergePagedItems(responses: readonly LotListResponse[]): LotSummary[] {
  const seenIds = new Set<string>()
  const merged: LotSummary[] = []
  for (const pageRes of responses) {
    for (const item of pageRes.items) {
      if (!seenIds.has(item.lot_id)) {
        seenIds.add(item.lot_id)
        merged.push(item)
      }
    }
  }
  return merged
}

export async function fetchLoadedPagesWindow(
  client: ApiClient,
  buildParams: (page: number) => LotListQueryParams,
  loadedPageCount: number,
  signal: AbortSignal,
): Promise<{ items: LotSummary[]; metaSource: LotListResponse }> {
  const firstPage = await client.lots.list(buildParams(1), { signal })
  const maxAvailablePages = Math.max(1, firstPage.pagination.total_pages)
  const targetLastPage = Math.min(Math.max(1, loadedPageCount), maxAvailablePages)

  if (targetLastPage <= 1 || firstPage.pagination.total_pages === 0) {
    return { items: firstPage.items, metaSource: firstPage }
  }

  const extraPages = await Promise.all(
    Array.from({ length: targetLastPage - 1 }, (_, index) =>
      client.lots.list(buildParams(index + 2), { signal }),
    ),
  )
  const allPages = [firstPage, ...extraPages]
  return {
    items: mergePagedItems(allPages),
    metaSource: allPages[allPages.length - 1] ?? firstPage,
  }
}

export async function executeChunkedBulkDelete(
  client: ApiClient,
  uniqueIds: readonly string[],
  isStale: () => boolean,
  onCompletedPartial: (removedIds: ReadonlySet<string>) => void,
): Promise<LotBulkDeleteResponse> {
  const deletedIds: string[] = []
  const notFoundIds: string[] = []

  try {
    for (let offset = 0; offset < uniqueIds.length; offset += BULK_DELETE_CHUNK_SIZE) {
      const chunk = uniqueIds.slice(offset, offset + BULK_DELETE_CHUNK_SIZE)
      const res = await client.lots.bulkDeleteLots({ lot_ids: chunk })
      if (isStale()) {
        return { deleted_ids: [], not_found_ids: [], deleted_count: 0 }
      }
      deletedIds.push(...res.deleted_ids)
      notFoundIds.push(...res.not_found_ids)
    }
  } finally {
    if (!isStale() && (deletedIds.length > 0 || notFoundIds.length > 0)) {
      onCompletedPartial(new Set([...deletedIds, ...notFoundIds]))
    }
  }

  return {
    deleted_ids: deletedIds,
    not_found_ids: notFoundIds,
    deleted_count: deletedIds.length,
  }
}
