export type TrafficLightColor = 'green' | 'yellow' | 'red'

export type AuctionHouse =
  | 'TAA'
  | 'USS'
  | 'CAA'
  | 'JU'
  | 'Honda'
  | 'ARAI'
  | 'MIRIVE'
  | 'KCAA'
  | 'LAA'
  | 'ORIX'
  | 'ZIP'
  | 'AUCNET'
  | 'OTHER'

export type ItemProcessingStatus = 'queued' | 'processing' | 'ready' | 'failed'

export type BatchStatus = 'queued' | 'processing' | 'completed' | 'partial_failed' | 'failed'

export type MascotMood = 'sleeping' | 'thinking' | 'happy' | 'confused' | 'warning'

export type TaskStep =
  | 'gatekeeper'
  | 'fast_header_ocr'
  | 'gemini_ocr'
  | 'cross_audit'
  | 'customs_calc'
  | 'farpost_parts'
  | 'drom_market'
  | 'scoring'
  | 'completed'
  | 'failed'

export type LotSortBy = 'created_at' | 'net_benefit' | 'turnkey_cost'

export type LotSortOrder = 'desc' | 'asc'

export interface LotListQueryParams {
  query?: string
  make?: string
  model?: string
  verdict?: TrafficLightColor
  has_anomaly?: boolean
  page?: number
  page_size?: number
  sort_by?: LotSortBy
  sort_order?: LotSortOrder
}

export interface LotSummary {
  lot_id: string
  make: string
  model: string
  year: number | null
  engine_cc: number | null
  frame_id: string
  auction_house: AuctionHouse
  lot_number: string
  overall_grade: string
  mileage_km: number | null
  turnkey_cost_rub: number
  market_price_rf_rub: number
  verdict: TrafficLightColor
  verdict_headline: string
  net_benefit_rub: number
  meti_sanction_risk: boolean
  has_anomaly: boolean
  anomaly_text: string | null
  thumbnail_url: string | null
  created_at: string
}

export interface InProgressItemPreview {
  batch_id: string
  lot_id: string | null
  display_title: string
  status: ItemProcessingStatus
  current_step: TaskStep
}

export interface InProgressSummary {
  active_batches_count: number
  total_processing_lots: number
  items: InProgressItemPreview[]
}

export interface PaginationMeta {
  total_items: number
  page: number
  page_size: number
  total_pages: number
}

export interface FilterCountItem {
  value: string
  count: number
}

export interface AvailableFilters {
  total_lots_count: number
  makes: FilterCountItem[]
  models: FilterCountItem[]
  counts_by_verdict: Partial<Record<TrafficLightColor, number>>
}

export interface LotListResponse {
  items: LotSummary[]
  in_progress: InProgressSummary
  pagination: PaginationMeta
  available_filters: AvailableFilters
}

export interface MascotState {
  mood: MascotMood
  phrase_ru: string
  badge_text: string
}

export interface BatchCreateResponse {
  batch_id: string
  total_items: number
  status: BatchStatus
  created_at: string
  poll_interval_ms: number
}

export interface BatchItemStatus {
  lot_id: string | null
  file_index: number
  original_filename: string
  preview_title: string | null
  status: ItemProcessingStatus
  current_step: TaskStep
  error_message: string | null
  summary: LotSummary | null
}

export interface BatchProgressResponse {
  batch_id: string
  status: BatchStatus
  mascot: MascotState
  total_count: number
  processed_count: number
  ready_count: number
  failed_count: number
  items: BatchItemStatus[]
}
