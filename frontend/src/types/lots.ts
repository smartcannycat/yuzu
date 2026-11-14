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

export type LotLifecycleFilter = 'active' | 'archived' | 'all'

export type LotArchiveReason = 'expired' | 'manual'

export interface LotListQueryParams {
  query?: string
  make?: string
  model?: string
  verdict?: TrafficLightColor
  has_anomaly?: boolean
  lifecycle?: LotLifecycleFilter
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
  auction_date: string | null
  is_archived: boolean
  archived_at: string | null
  archived_reason: LotArchiveReason | null
  expires_at: string | null
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
  archived_lots_count: number
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

export type OdometerStatus = 'confirmed' | 'replaced' | 'tampered' | 'unknown'
export type DriveType = '2WD' | '4WD'
export type FuelType = 'gasoline' | 'hybrid' | 'diesel' | 'ev' | 'other'
export type AgeCorridor = 'under_3_years' | '3_to_5_years' | 'over_5_years'
export type CrossAuditStatus =
  | 'clean'
  | 'anomaly_detected'
  | 'not_found'
  | 'live_only'
  | 'unavailable'
export type RiskLevel = 'CLEAN' | 'INFO' | 'WARNING' | 'CRITICAL'
export type ChecklistItemStatus = 'ok' | 'warning' | 'critical' | 'unknown'

export type BodyPanel =
  | 'front_bumper'
  | 'rear_bumper'
  | 'hood'
  | 'roof'
  | 'tailgate'
  | 'front_left_fender'
  | 'front_right_fender'
  | 'front_left_door'
  | 'front_right_door'
  | 'rear_left_door'
  | 'rear_right_door'
  | 'rear_left_quarter'
  | 'rear_right_quarter'
  | 'left_sill'
  | 'right_sill'
  | 'windshield'

export interface NormalizedDefect {
  panel_id: BodyPanel
  panel_ru: string
  defect_types: string[]
  severity: number | null
  raw_code: string
  description_ru: string
}

export interface RiskFlags {
  is_flooded: boolean
  airbag_deployed: boolean
  hail_damage: boolean
  underbody_corrosion: boolean
  pillar_or_frame_repair: boolean
  core_support_repair: boolean
  underbody_rust: boolean
  panel_needs_replacement_x: boolean
  panel_replaced_xx: boolean
  odometer_issue: boolean
  color_changed: boolean
  windshield_damage: boolean
  repaired_grade_r_ra: boolean
}

export interface NormalizedSheet {
  lot_number: string
  auction_house: AuctionHouse
  auction_branch: string | null
  auction_date: string | null
  auction_strictness_index: number
  make: string
  model: string
  trim: string | null
  model_code: string
  chassis_number: string
  frame_id: string
  frame_id_confidence: 'exact' | 'synthesized' | 'raw'
  first_reg_year: number | null
  first_reg_month: number | null
  first_reg_date_str: string | null
  is_pass_corridor_3_5: boolean | null
  engine_cc: number | null
  power_hp: number | null
  power_hp_source: 'drom_catalog' | 'katashiki_cache' | 'manual' | null
  is_under_160_hp: boolean | null
  mileage_km: number | null
  odometer_status: OdometerStatus
  transmission: string
  drive_type: DriveType | null
  fuel_type: FuelType | null
  color_ru: string | null
  paint_code: string | null
  overall_grade: string
  exterior_grade: string | null
  interior_grade: string | null
  shaken_until: string | null
  recycling_fee_yen: number | null
  recycling_fee_paid: boolean | null
  equipment_ru: string[]
  defects: NormalizedDefect[]
  risk_flags: RiskFlags
  inspector_notes_ru: string[]
  inspector_notes_raw: string[]
  seller_comments_ru: string[]
  extra_ru: string[]
  ocr_warnings: string[]
  low_confidence_fields: string[]
}

export interface AnomalyAlert {
  type: string
  severity: 'critical' | 'warning' | 'info'
  title_ru: string
  message_ru: string
  diff_details: Record<string, string | number | null> | null
}

export interface PastAuctionRecord {
  auction_date: string
  auction_house: string
  auction_strictness: number | null
  lot_number: string
  overall_grade: string
  mileage_km: number | null
  defects_summary: string | null
  closing_price_jpy: number | null
  sheet_archive_url: string | null
}

export interface CrossAuditReport {
  status: CrossAuditStatus
  source_name: string
  is_archive_available: boolean
  risk_level: RiskLevel
  has_critical_anomaly: boolean
  headline_ru: string
  times_auctioned: number
  verified_at: string
  anomalies: AnomalyAlert[]
  history: PastAuctionRecord[]
}

export interface DamagedPartItem {
  panel_id: BodyPanel
  defect_code: string
  part_name_ru: string
  subtitle_ru: string | null
  price_from_rub: number
  in_stock_vladivostok: boolean
  is_statistical_fallback: boolean
}

export interface ServiceWorkItem {
  work_type: 'mount_dismount' | 'paint' | 'pdr_and_polish' | 'bodywork'
  label_ru: string
  amount_rub: number
  zero_cost_reason_ru: string | null
}

export interface FarpostRepairSummary {
  parts: DamagedPartItem[]
  service_works: ServiceWorkItem[]
  total_parts_from_rub: number
  total_works_rub: number
  grand_total_repair_rub: number
  has_color_matched_parts: boolean
  included_in_turnkey_hint_ru: string
}

export interface WiseCostStep {
  step_number: number
  name_ru: string
  amount_rub: number
  original_currency: string | null
  original_amount: number | null
  is_optional: boolean
}

export interface WiseCostLadder {
  car_bid_jpy: number
  car_bid_rub: number
  turnkey_cost_rub: number
  market_price_rf_rub: number
  net_benefit_rub: number
  benefit_percentage: number
  steps: WiseCostStep[]
}

export interface MarketComparisonInfo {
  market_price_rf_rub: number
  analogs_count: number
  price_min_rub: number | null
  price_max_rub: number | null
  search_region_ru: string
  excludes_under_order: boolean
  filtered_out_under_order_count: number
  is_fallback: boolean
  fallback_reason_ru: string | null
  drom_search_url: string
}

export interface CurrencyRates {
  jpy_rub_bank: number
  jpy_rate_source: string
  eur_rub_cbrf: number
  usd_rub_cbrf: number
  cbrf_date: string
}

export interface CustomsCalculation {
  age_corridor: AgeCorridor
  duty_calculation_mode: 'eur_per_cc' | 'pct_of_value'
  engine_cc: number
  duty_rate_eur_per_cc: number | null
  effective_duty_pct: number | null
  customs_duty_eur: number
  customs_duty_rub: number
  excise_rub: number
  import_vat_rub: number
  is_under_160_hp: boolean | null
  is_commercial_util: boolean
  utilization_fee_rub: number
  customs_clearance_fee_rub: number
  freight_vladivostok_rub: number
  broker_svh_sbkts_rub: number
  meti_sanction_risk: boolean
  rates_snapshot: CurrencyRates
}

export interface TrafficLightVerdict {
  verdict: TrafficLightColor
  headline: string
  short_verdict_label: string
  badge_text: string
  net_benefit_rub: number
  benefit_percentage: number
  body_summary_ru: string
  interior_summary_ru: string
  reasoning_bullets: string[]
}

export interface SafetyCheckItem {
  system_key:
    | 'structural_frame'
    | 'airbags_srs'
    | 'engine_transmission'
    | 'underbody_corrosion'
    | 'flood_or_fire'
  label_ru: string
  status: ChecklistItemStatus
  detail_ru: string
}

export interface SafetyChecklist {
  overall_status: ChecklistItemStatus
  overall_label_ru: string
  items: SafetyCheckItem[]
}

export interface LotMediaLinks {
  sheet_thumbnail_url: string
  sheet_scan_url: string
  drom_search_url: string
}

export interface EconomicsDetail {
  bid_slider_min_jpy: number
  bid_slider_max_jpy: number
  bid_slider_step_jpy: number
  is_repairs_included: boolean
  is_simulation_modified?: boolean
  customs: CustomsCalculation
  farpost_repair: FarpostRepairSummary
  wise_cost_ladder: WiseCostLadder
}

export interface LotDetailResponse {
  lot_id: string
  created_at: string
  updated_at: string
  is_archived: boolean
  archived_at: string | null
  archived_reason: LotArchiveReason | null
  expires_at: string | null
  passport: NormalizedSheet
  verdict: TrafficLightVerdict
  market: MarketComparisonInfo
  audit: CrossAuditReport
  safety_checklist: SafetyChecklist
  economics: EconomicsDetail
  media: LotMediaLinks
}

export interface RecalculateRequest {
  bid_jpy?: number
  bid_rub?: number
  is_commercial_util?: boolean
  include_repairs?: boolean
  custom_power_hp?: number
  custom_freight_rub?: number
}

export interface RecalculateResponse {
  lot_id: string
  recalculated_at: string
  applied_bid_jpy: number
  applied_bid_rub: number
  is_commercial_util: boolean
  include_repairs: boolean
  customs: CustomsCalculation
  wise_cost_ladder: WiseCostLadder
  turnkey_cost_rub: number
  market_price_rf_rub: number
  net_benefit_rub: number
  benefit_percentage: number
  verdict: TrafficLightVerdict
  is_simulation_modified?: boolean
  pdf_report_stale: boolean
}

export interface LotLifecyclePatchRequest {
  is_archived: boolean
}

export interface LotBulkDeleteRequest {
  lot_ids: string[]
}

export interface LotBulkDeleteResponse {
  deleted_ids: string[]
  not_found_ids: string[]
  deleted_count: number
}
