import { delay } from '@/api/mock/helpers'
import { buildMockLotDetail, recalculateMockLotDetail } from '@/api/mock/lotDetails'
import { createMockLotsWorkspace } from '@/api/mock/lotsBatches'
import { MOCK_IN_PROGRESS_SUMMARY, SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import type { LotsApi } from '@/api/types'
import {
  ApiError,
  type AvailableFilters,
  type BatchCreateResponse,
  type BatchProgressResponse,
  type FilterCountItem,
  type InProgressSummary,
  type LotDetailResponse,
  type LotListQueryParams,
  type LotListResponse,
  type LotSummary,
  type RecalculateRequest,
  type RecalculateResponse,
  type TrafficLightColor,
} from '@/types/api'

type FilterFacet = 'make' | 'model' | 'verdict'

interface NormalizedFilters {
  query: string
  make: string
  model: string
  verdict?: TrafficLightColor
  hasAnomaly?: boolean
}

function normalizeFilters(params: LotListQueryParams): NormalizedFilters {
  return {
    query: params.query?.trim().toLowerCase() ?? '',
    make: params.make?.trim().toLowerCase() ?? '',
    model: params.model?.trim().toLowerCase() ?? '',
    verdict: params.verdict,
    hasAnomaly: params.has_anomaly,
  }
}

function matchesLotFilters(
  lot: LotSummary,
  filters: NormalizedFilters,
  excludedFacets: ReadonlySet<FilterFacet> = new Set(),
): boolean {
  if (filters.query) {
    const searchable = [
      lot.make,
      lot.model,
      lot.frame_id,
      lot.lot_number,
      lot.auction_house,
      lot.verdict_headline,
    ]
      .join(' ')
      .toLowerCase()
    if (!searchable.includes(filters.query)) {
      return false
    }
  }

  if (!excludedFacets.has('make') && filters.make && lot.make.toLowerCase() !== filters.make) {
    return false
  }

  if (!excludedFacets.has('model') && filters.model && lot.model.toLowerCase() !== filters.model) {
    return false
  }

  if (!excludedFacets.has('verdict') && filters.verdict && lot.verdict !== filters.verdict) {
    return false
  }

  if (typeof filters.hasAnomaly === 'boolean' && lot.has_anomaly !== filters.hasAnomaly) {
    return false
  }

  return true
}

function buildFilterCounts(lots: readonly LotSummary[], key: 'make' | 'model'): FilterCountItem[] {
  const counts = new Map<string, number>()
  for (const lot of lots) {
    const val = lot[key]
    counts.set(val, (counts.get(val) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'ru'))
}

function buildAvailableFilters(
  allLots: readonly LotSummary[],
  filters: NormalizedFilters,
): AvailableFilters {
  const makeFacetLots = allLots.filter((lot) =>
    matchesLotFilters(lot, filters, new Set<FilterFacet>(['make', 'model'])),
  )
  const makeCounts = new Map<string, number>()
  for (const lot of allLots) {
    if (!makeCounts.has(lot.make)) {
      makeCounts.set(lot.make, 0)
    }
  }
  for (const lot of makeFacetLots) {
    makeCounts.set(lot.make, (makeCounts.get(lot.make) ?? 0) + 1)
  }
  const makes: FilterCountItem[] = Array.from(makeCounts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'ru'))

  const modelFacetLots = allLots.filter((lot) =>
    matchesLotFilters(lot, filters, new Set<FilterFacet>(['model'])),
  )
  const models = buildFilterCounts(modelFacetLots, 'model')

  if (filters.model && !models.some((item) => item.value.toLowerCase() === filters.model)) {
    const activeModelLot = allLots.find(
      (lot) =>
        lot.model.toLowerCase() === filters.model &&
        (!filters.make || lot.make.toLowerCase() === filters.make),
    )
    if (activeModelLot) {
      models.push({ value: activeModelLot.model, count: 0 })
    }
  }

  const verdictFacetLots = allLots.filter((lot) =>
    matchesLotFilters(lot, filters, new Set<FilterFacet>(['verdict'])),
  )
  const countsByVerdict: Partial<Record<TrafficLightColor, number>> = {
    green: 0,
    yellow: 0,
    red: 0,
  }
  for (const lot of verdictFacetLots) {
    countsByVerdict[lot.verdict] = (countsByVerdict[lot.verdict] ?? 0) + 1
  }

  return {
    total_lots_count: makeFacetLots.length,
    makes,
    models,
    counts_by_verdict: countsByVerdict,
  }
}

export function queryMockLots(
  params: LotListQueryParams = {},
  sourceLots: readonly LotSummary[] = SEEDED_MOCK_LOTS,
  inProgress: InProgressSummary = MOCK_IN_PROGRESS_SUMMARY,
): LotListResponse {
  const filters = normalizeFilters(params)
  const filtered = sourceLots.filter((lot) => matchesLotFilters(lot, filters))

  const sortBy = params.sort_by ?? 'created_at'
  const sortOrder = params.sort_order ?? 'desc'
  const direction = sortOrder === 'asc' ? 1 : -1

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'net_benefit') {
      return (a.net_benefit_rub - b.net_benefit_rub) * direction
    }
    if (sortBy === 'turnkey_cost') {
      return (a.turnkey_cost_rub - b.turnkey_cost_rub) * direction
    }
    return (Date.parse(a.created_at) - Date.parse(b.created_at)) * direction
  })

  const page = Math.max(1, params.page ?? 1)
  const pageSize = Math.max(1, Math.min(100, params.page_size ?? 20))
  const totalItems = sorted.length
  const totalPages = Math.ceil(totalItems / pageSize)
  const offset = (page - 1) * pageSize

  return {
    items: sorted.slice(offset, offset + pageSize),
    in_progress: inProgress,
    pagination: {
      total_items: totalItems,
      page,
      page_size: pageSize,
      total_pages: totalPages,
    },
    available_filters: buildAvailableFilters(sourceLots, filters),
  }
}

export function createMockLotsApi(defaultDelay: number, persistState = false): LotsApi {
  const workspace = createMockLotsWorkspace({ persistState })
  const detailCache = new Map<string, LotDetailResponse>()

  function resolveLotDetail(lotId: string): LotDetailResponse {
    const cached = detailCache.get(lotId)
    if (cached) return cached

    const snapshot = workspace.getFeedSnapshot()
    const summary = snapshot.lots.find((item) => item.lot_id === lotId)
    if (!summary) {
      throw new ApiError({
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        detail: 'Лот не найден.',
      })
    }

    const detail = buildMockLotDetail(summary)
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
      const base = resolveLotDetail(lotId)
      return recalculateMockLotDetail(base, payload)
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
