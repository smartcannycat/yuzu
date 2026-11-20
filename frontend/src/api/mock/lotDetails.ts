import {
  DEFAULT_RISK_FLAGS,
  buildFarpostRepairSummary,
  buildMockCrossAudit,
  buildMockCustoms,
  buildSafetyChecklist,
} from '@/api/mock/lotDetailBuilders'
import { PANEL_LABELS_RU, PRESET_CONFIGS } from '@/api/mock/lotDetailsPresets'
import {
  COMMERCIAL_UTIL_FEE_RUB,
  EUR_RUB_RATE,
  JPY_RUB_RATE,
  MIN_BID_JPY,
  PERSONAL_UTIL_FEE_RUB,
  buildWiseSteps,
  formatVerdictBadgeText,
  recalculateMockLotDetail,
} from '@/api/mock/lotEconomicsCalc'
import { buildMockSheetSvgDataUrl } from '@/api/mock/lotSheetSvg'
import type {
  EconomicsDetail,
  LotDetailResponse,
  LotSummary,
  NormalizedDefect,
  NormalizedSheet,
  RiskFlags,
  TrafficLightVerdict,
} from '@/types/api'

export { recalculateMockLotDetail }

export function buildMockLotDetail(summary: LotSummary): LotDetailResponse {
  const preset = PRESET_CONFIGS[summary.lot_id]
  const riskFlags: RiskFlags = {
    ...DEFAULT_RISK_FLAGS,
    repaired_grade_r_ra: summary.overall_grade === 'R' || summary.overall_grade === 'RA',
    ...preset?.riskFlagsOverride,
  }

  const farpostRepair = buildFarpostRepairSummary(summary, preset)
  const repairTotal = farpostRepair.grand_total_repair_rub

  const engineCc = summary.engine_cc ?? 1496
  const powerHp = preset?.powerHp ?? (engineCc > 1900 ? 185 : 122)
  const isUnder160 = powerHp <= 160
  const isCommercialUtil = preset?.isCommercialUtilDefault ?? !isUnder160

  const freightRub = summary.meti_sanction_risk ? 155_000 : 95_000
  const japanFeeJpy = 85_000
  const japanFeeRub = Math.round(japanFeeJpy * JPY_RUB_RATE)
  const dutyRateEurPerCc =
    engineCc <= 1500 ? 1.7 : engineCc <= 1800 ? 2.5 : engineCc <= 2300 ? 2.7 : 3.0
  const customsDutyEur = Number((engineCc * dutyRateEurPerCc).toFixed(2))
  const customsDutyRub = Math.round(customsDutyEur * EUR_RUB_RATE)
  const utilFeeRub = isCommercialUtil ? COMMERCIAL_UTIL_FEE_RUB : PERSONAL_UTIL_FEE_RUB
  const brokerAndSvhRub = 48_000

  const fixedCostsRub =
    japanFeeRub + freightRub + customsDutyRub + utilFeeRub + brokerAndSvhRub + repairTotal
  const rawBidRub = Math.max(0, summary.turnkey_cost_rub - fixedCostsRub)
  const carBidJpy = Math.max(MIN_BID_JPY, Math.round(rawBidRub / JPY_RUB_RATE / 10_000) * 10_000)
  const carBidRub = Math.round(carBidJpy * JPY_RUB_RATE)

  const steps = buildWiseSteps({
    bidJpy: carBidJpy,
    bidRub: carBidRub,
    japanFeeJpy,
    japanFeeRub,
    freightRub,
    customsDutyEur,
    customsDutyRub,
    utilFeeRub,
    brokerAndSvhRub,
    repairRub: repairTotal,
    includeRepairs: true,
  })

  const turnkeyCostRub = steps.reduce((acc, step) => acc + step.amount_rub, 0)
  const netBenefitRub = summary.market_price_rf_rub - turnkeyCostRub
  const benefitPct = turnkeyCostRub > 0 ? (netBenefitRub / turnkeyCostRub) * 100 : 0

  const defects: NormalizedDefect[] = preset?.defects ?? [
    {
      panel_id: 'front_bumper',
      panel_ru: PANEL_LABELS_RU.front_bumper,
      defect_types: ['A'],
      severity: 1,
      raw_code: 'A1',
      description_ru: 'Передний бампер — незначительная царапина по лаку',
    },
  ]

  const passport: NormalizedSheet = {
    lot_number: summary.lot_number,
    auction_house: summary.auction_house,
    auction_branch: preset?.auctionBranch ?? `${summary.auction_house} Japan`,
    auction_date: summary.auction_date,
    auction_strictness_index: preset?.strictness ?? 0.8,
    make: summary.make,
    model: summary.model,
    trim: preset?.trim ?? null,
    model_code: preset?.modelCode ?? `${summary.frame_id.split('-')[0] ?? 'JDM'}`,
    chassis_number: summary.frame_id,
    frame_id: summary.frame_id,
    frame_id_confidence: 'exact',
    first_reg_year: summary.year,
    first_reg_month: 6,
    first_reg_date_str: summary.year ? `06.${summary.year} (3–5 лет, ЕАЭС)` : null,
    is_pass_corridor_3_5: true,
    engine_cc: engineCc,
    power_hp: powerHp,
    power_hp_source: 'drom_catalog',
    is_under_160_hp: isUnder160,
    mileage_km: summary.mileage_km,
    odometer_status: riskFlags.odometer_issue ? 'tampered' : 'confirmed',
    transmission: preset?.transmission ?? 'Вариатор (CVT)',
    drive_type: preset?.driveType ?? '2WD',
    fuel_type: preset?.fuelType ?? 'gasoline',
    color_ru: preset?.colorRu ?? 'Белый перламутр',
    paint_code: preset?.paintCode ?? '070',
    overall_grade: summary.overall_grade,
    exterior_grade: preset?.exteriorGrade ?? 'B',
    interior_grade: preset?.interiorGrade ?? 'B',
    shaken_until: preset?.shakenUntil ?? null,
    recycling_fee_yen: preset?.recyclingYen ?? 10800,
    recycling_fee_paid: true,
    equipment_ru: preset?.equipment ?? [
      'Климат-контроль',
      'Камера заднего вида',
      'Бесключевой доступ',
    ],
    defects,
    risk_flags: riskFlags,
    inspector_notes_ru: preset?.inspectorNotesRu ?? [
      'Кузов и оптика соответствуют заявленной оценке аукционного листа',
      'Двигатель и трансмиссия без замечаний по холодному пуску',
    ],
    inspector_notes_raw: preset?.inspectorNotesRaw ?? ['外装小キズ', '機関良好'],
    seller_comments_ru: preset?.sellerCommentsRu ?? ['Один владелец в Японии'],
    extra_ru: ['Два комплекта ключей'],
    ocr_warnings: preset?.ocrWarnings ?? [],
    low_confidence_fields: [],
  }

  const verdict: TrafficLightVerdict = {
    verdict: summary.verdict,
    headline:
      summary.verdict === 'green'
        ? 'РЕКОМЕНДОВАНО К ПОКУПКЕ'
        : summary.verdict === 'yellow'
          ? 'ПОД ВОПРОСОМ — ТРЕБУЕТ ВНИМАНИЯ'
          : 'ВЫСОКИЙ РИСК — ПОКУПКА НЕ РЕКОМЕНДОВАНА',
    short_verdict_label: summary.verdict_headline,
    badge_text: formatVerdictBadgeText(netBenefitRub),
    net_benefit_rub: netBenefitRub,
    benefit_percentage: Number(benefitPct.toFixed(1)),
    body_summary_ru:
      preset?.bodySummaryRu ??
      (summary.anomaly_text || 'Силовая структура без нареканий, мелкие эксплуатационные отметки'),
    interior_summary_ru:
      preset?.interiorSummaryRu ??
      `Оценка салона ${passport.interior_grade ?? 'B'} — ухоженное состояние`,
    reasoning_bullets: preset?.reasoningBullets ?? [
      `Лист площадки ${summary.auction_house} (индекс строгости ${passport.auction_strictness_index.toFixed(2)})`,
      `Пробег ${summary.mileage_km ? `${summary.mileage_km.toLocaleString('ru-RU')} км` : '—'} подтверждён`,
    ],
  }

  const customs = buildMockCustoms({
    engineCc,
    dutyRateEurPerCc,
    customsDutyEur,
    customsDutyRub,
    isUnder160,
    isCommercialUtil,
    utilFeeRub,
    freightRub,
    brokerAndSvhRub,
    metiSanctionRisk: summary.meti_sanction_risk,
  })

  const economics: EconomicsDetail = {
    bid_slider_min_jpy: Math.max(MIN_BID_JPY, Math.round((carBidJpy * 0.55) / 10_000) * 10_000),
    bid_slider_max_jpy: Math.max(
      carBidJpy + 500_000,
      Math.round((carBidJpy * 1.65) / 10_000) * 10_000,
    ),
    bid_slider_step_jpy: 10_000,
    is_repairs_included: true,
    customs,
    farpost_repair: farpostRepair,
    wise_cost_ladder: {
      car_bid_jpy: carBidJpy,
      car_bid_rub: carBidRub,
      turnkey_cost_rub: turnkeyCostRub,
      market_price_rf_rub: summary.market_price_rf_rub,
      net_benefit_rub: netBenefitRub,
      benefit_percentage: Number(benefitPct.toFixed(1)),
      steps,
    },
  }

  const audit = buildMockCrossAudit(summary, passport, defects, carBidJpy, preset)
  const sheetDataUrl = buildMockSheetSvgDataUrl(summary, passport)
  const dromQuery = encodeURIComponent(`${summary.make} ${summary.model}`)

  return {
    lot_id: summary.lot_id,
    created_at: summary.created_at,
    updated_at: summary.archived_at ?? summary.created_at,
    is_archived: summary.is_archived,
    archived_at: summary.archived_at,
    archived_reason: summary.archived_reason,
    expires_at: summary.expires_at,
    passport,
    verdict,
    market: {
      market_price_rf_rub: summary.market_price_rf_rub,
      analogs_count: preset?.analogsCount ?? 10,
      price_min_rub: Math.round(summary.market_price_rf_rub * 0.89),
      price_max_rub: Math.round(summary.market_price_rf_rub * 1.12),
      search_region_ru: 'ДФО / Владивосток',
      excludes_under_order: true,
      filtered_out_under_order_count: 5,
      is_fallback: false,
      fallback_reason_ru: null,
      drom_search_url: `https://auto.drom.ru/all/?q=${dromQuery}`,
    },
    audit,
    safety_checklist: buildSafetyChecklist(riskFlags),
    economics,
    media: {
      sheet_thumbnail_url: summary.thumbnail_url ?? sheetDataUrl,
      sheet_scan_url: sheetDataUrl,
      drom_search_url: `https://auto.drom.ru/all/?q=${dromQuery}`,
    },
  }
}
