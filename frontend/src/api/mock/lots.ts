import { delay } from '@/api/mock/helpers'
import { MOCK_IN_PROGRESS_SUMMARY, SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import type { LotsApi } from '@/api/types'
import type {
  AvailableFilters,
  FilterCountItem,
  LotListQueryParams,
  LotListResponse,
  LotSummary,
  TrafficLightColor,
} from '@/types/api'

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

function buildAvailableFilters(lots: readonly LotSummary[]): AvailableFilters {
  const countsByVerdict: Partial<Record<TrafficLightColor, number>> = {
    green: 0,
    yellow: 0,
    red: 0,
  }
  for (const lot of lots) {
    countsByVerdict[lot.verdict] = (countsByVerdict[lot.verdict] ?? 0) + 1
  }

  return {
    total_lots_count: lots.length,
    makes: buildFilterCounts(lots, 'make'),
    models: buildFilterCounts(lots, 'model'),
    counts_by_verdict: countsByVerdict,
  }
}

export function queryMockLots(params: LotListQueryParams = {}): LotListResponse {
  const normalizedQuery = params.query?.trim().toLowerCase() ?? ''
  const normalizedMake = params.make?.trim().toLowerCase() ?? ''
  const normalizedModel = params.model?.trim().toLowerCase() ?? ''

  const filtered = SEEDED_MOCK_LOTS.filter((lot) => {
    if (normalizedQuery) {
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
      if (!searchable.includes(normalizedQuery)) {
        return false
      }
    }

    if (normalizedMake && lot.make.toLowerCase() !== normalizedMake) {
      return false
    }

    if (normalizedModel && lot.model.toLowerCase() !== normalizedModel) {
      return false
    }

    if (params.verdict && lot.verdict !== params.verdict) {
      return false
    }

    if (typeof params.has_anomaly === 'boolean' && lot.has_anomaly !== params.has_anomaly) {
      return false
    }

    return true
  })

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
    in_progress: MOCK_IN_PROGRESS_SUMMARY,
    pagination: {
      total_items: totalItems,
      page,
      page_size: pageSize,
      total_pages: totalPages,
    },
    available_filters: buildAvailableFilters(SEEDED_MOCK_LOTS),
  }
}

export function createMockLotsApi(defaultDelay: number): LotsApi {
  return {
    async list(params?: LotListQueryParams): Promise<LotListResponse> {
      await delay(Math.min(defaultDelay, 160))
      return queryMockLots(params)
    },
  }
}
