import type { components, operations } from '@/types/api.generated'

type Schemas = components['schemas']
type ListLotsQuery = NonNullable<operations['lot_list_lots']['parameters']['query']>

type WithRequired<T, K extends keyof T> = Omit<T, K> & {
  [P in K]-?: Exclude<T[P], undefined>
}

type WithOptional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>

type WithoutNullProps<T> = {
  [K in keyof T]: Exclude<T[K], null>
}

// Pydantic emits `?: T | null` for nullable fields with `= None` that are always present in JSON responses.
type RequiredNullableProps<T> = {
  [K in keyof T]-?: undefined extends T[K]
    ? null extends T[K]
      ? Exclude<T[K], undefined>
      : T[K]
    : T[K]
}

export type TrafficLightColor = Schemas['TrafficLightColor']
export type AuctionHouse = Schemas['AuctionHouse']
export type ItemProcessingStatus = Schemas['ItemProcessingStatus']
export type BatchStatus = Schemas['BatchStatus']
export type MascotMood = Schemas['MascotMood']
export type TaskStep = Schemas['TaskStep']
export type LotLifecycleFilter = Schemas['LotLifecycleFilter']
export type LotArchiveReason = Schemas['LotArchiveReason']
export type PowerHpSource = Schemas['PowerHpSource']
export type OdometerStatus = Schemas['OdometerStatus']
export type DriveType = Schemas['DriveType']
export type FuelType = Schemas['FuelType']
export type AgeCorridor = Schemas['AgeCorridor']
export type CrossAuditStatus = Schemas['CrossAuditStatus']
export type RiskLevel = Schemas['RiskLevel']
export type ChecklistItemStatus = Schemas['ChecklistItemStatus']
export type BodyPanel = Schemas['BodyPanel']
export type PartSourceKind = Schemas['PartSourceKind']
export type UtilFeeType = Schemas['UtilFeeType']
export type DutyCalculationMode = Schemas['DutyCalculationMode']
export type AnomalySeverity = Schemas['AnomalySeverity']
export type SystemKey = Schemas['SystemKey']
export type WorkType = Schemas['WorkType']

export type LotSortBy = NonNullable<ListLotsQuery['sort_by']>
export type LotSortOrder = NonNullable<ListLotsQuery['sort_order']>
export type LotListQueryParams = WithoutNullProps<ListLotsQuery>

export type LotSummary = RequiredNullableProps<Schemas['LotSummary']>
export type InProgressItemPreview = RequiredNullableProps<Schemas['InProgressItemPreview']>
export type InProgressSummary = WithRequired<
  Omit<Schemas['InProgressSummary'], 'items'> & { items?: InProgressItemPreview[] },
  'items'
>
export type PaginationMeta = Schemas['PaginationMeta']
export type FilterCountItem = Schemas['FilterCountItem']

export type AvailableFilters = WithRequired<
  Omit<Schemas['AvailableFilters'], 'counts_by_verdict'> & {
    counts_by_verdict: Partial<Record<TrafficLightColor, number>>
  },
  'makes' | 'models'
>

export type LotListResponse = Omit<
  Schemas['LotListResponse'],
  'items' | 'in_progress' | 'available_filters'
> & {
  items: LotSummary[]
  in_progress: InProgressSummary
  available_filters: AvailableFilters
}

export type MascotState = Schemas['MascotState']
export type BatchCreateResponse = Schemas['BatchCreateResponse']
export type BatchItemStatus = RequiredNullableProps<
  Omit<Schemas['BatchItemStatus'], 'summary'> & { summary?: LotSummary | null }
>
export type BatchProgressResponse = Omit<Schemas['BatchProgressResponse'], 'items'> & {
  items: BatchItemStatus[]
}

export type NormalizedDefect = RequiredNullableProps<Schemas['NormalizedDefect']>
export type RiskFlags = Schemas['RiskFlags']
export type NormalizedSheet = RequiredNullableProps<
  WithRequired<
    Omit<Schemas['NormalizedSheet'], 'defects'> & { defects?: NormalizedDefect[] },
    | 'defects'
    | 'equipment_ru'
    | 'inspector_notes_ru'
    | 'inspector_notes_raw'
    | 'seller_comments_ru'
    | 'extra_ru'
    | 'ocr_warnings'
    | 'low_confidence_fields'
  >
>

export type AnomalyAlert = RequiredNullableProps<Schemas['AnomalyAlert']>
export type PastAuctionRecord = RequiredNullableProps<Schemas['PastAuctionRecord']>
export type CrossAuditReport = WithRequired<
  Omit<Schemas['CrossAuditReport'], 'anomalies' | 'history'> & {
    anomalies?: AnomalyAlert[]
    history?: PastAuctionRecord[]
  },
  'anomalies' | 'history'
>

export type DamagedPartItem = RequiredNullableProps<Schemas['DamagedPartItem']>
export type ServiceWorkItem = RequiredNullableProps<Schemas['ServiceWorkItem']>
export type FarpostRepairSummary = WithRequired<
  Omit<Schemas['FarpostRepairSummary'], 'parts' | 'service_works'> & {
    parts?: DamagedPartItem[]
    service_works?: ServiceWorkItem[]
  },
  'parts' | 'service_works'
>

export type WiseCostStep = RequiredNullableProps<Schemas['WiseCostStep']>
export type WiseCostLadder = Omit<Schemas['WiseCostLadder'], 'steps'> & {
  steps: WiseCostStep[]
}
export type MarketComparisonInfo = RequiredNullableProps<Schemas['MarketComparisonInfo']>
export type CurrencyRates = Schemas['CurrencyRates']
export type CustomsCalculation = RequiredNullableProps<Schemas['CustomsCalculation']>
export type TrafficLightVerdict = WithRequired<Schemas['TrafficLightVerdict'], 'reasoning_bullets'>
export type SafetyCheckItem = Schemas['SafetyCheckItem']
export type SafetyChecklist = Schemas['SafetyChecklist']
export type LotMediaLinks = Schemas['LotMediaLinks']

export type EconomicsDetail = WithOptional<
  Omit<Schemas['EconomicsDetail'], 'customs' | 'farpost_repair' | 'wise_cost_ladder'> & {
    customs: CustomsCalculation
    farpost_repair: FarpostRepairSummary
    wise_cost_ladder: WiseCostLadder
  },
  'is_simulation_modified'
>

export type LotDetailResponse = RequiredNullableProps<
  Omit<Schemas['LotDetailResponse'], 'passport' | 'verdict' | 'market' | 'audit' | 'economics'> & {
    passport: NormalizedSheet
    verdict: TrafficLightVerdict
    market: MarketComparisonInfo
    audit: CrossAuditReport
    economics: EconomicsDetail
  }
>

export type RecalculateRequest = Partial<
  Pick<Schemas['RecalculateRequest'], 'include_repairs' | 'is_commercial_util'>
> &
  Omit<Schemas['RecalculateRequest'], 'include_repairs' | 'is_commercial_util'>

export type RecalculateResponse = WithOptional<
  RequiredNullableProps<
    Omit<Schemas['RecalculateResponse'], 'customs' | 'wise_cost_ladder' | 'verdict'> & {
      customs: CustomsCalculation
      wise_cost_ladder: WiseCostLadder
      verdict: TrafficLightVerdict
    }
  >,
  | 'bid_slider_min_jpy'
  | 'is_simulation_modified'
  | 'power_hp'
  | 'power_hp_source'
  | 'is_under_160_hp'
  | 'ocr_warnings'
>

export type LotLifecyclePatchRequest = Schemas['LotLifecyclePatchRequest']
export type LotBulkDeleteRequest = Schemas['LotBulkDeleteRequest']
export type LotBulkDeleteResponse = WithRequired<Schemas['LotBulkDeleteResponse'], 'not_found_ids'>
