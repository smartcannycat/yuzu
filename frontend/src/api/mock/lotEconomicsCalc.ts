import type {
  CustomsCalculation,
  LotDetailResponse,
  RecalculateRequest,
  RecalculateResponse,
  RiskFlags,
  TrafficLightColor,
  TrafficLightVerdict,
  WiseCostStep,
} from '@/types/api'
import { formatRub } from '@/utils/formatters'

export const JPY_RUB_RATE = 0.642
export const EUR_RUB_RATE = 95.0
export const USD_RUB_RATE = 88.5
export const COMMERCIAL_UTIL_FEE_RUB = 528_000
export const PERSONAL_UTIL_FEE_RUB = 5_200

export function formatVerdictBadgeText(netBenefitRub: number): string {
  return netBenefitRub >= 0
    ? `Выгода: ${formatRub(netBenefitRub, { signed: true })}`
    : `Переплата: ${formatRub(Math.abs(netBenefitRub))}`
}

export function buildWiseSteps(params: {
  bidJpy: number
  bidRub: number
  japanFeeJpy: number
  japanFeeRub: number
  freightRub: number
  customsDutyEur: number
  customsDutyRub: number
  utilFeeRub: number
  brokerAndSvhRub: number
  repairRub: number
  includeRepairs: boolean
}): WiseCostStep[] {
  return [
    {
      step_number: 1,
      name_ru: 'Ставка на аукционе (FOB Япония)',
      amount_rub: params.bidRub,
      original_currency: 'JPY',
      original_amount: params.bidJpy,
      is_optional: false,
    },
    {
      step_number: 2,
      name_ru: 'Аукционный сбор и логистика по Японии',
      amount_rub: params.japanFeeRub,
      original_currency: 'JPY',
      original_amount: params.japanFeeJpy,
      is_optional: false,
    },
    {
      step_number: 3,
      name_ru: 'Морской фрахт в порт Владивосток',
      amount_rub: params.freightRub,
      original_currency: null,
      original_amount: null,
      is_optional: false,
    },
    {
      step_number: 4,
      name_ru: 'Таможенная пошлина ЕАЭС',
      amount_rub: params.customsDutyRub,
      original_currency: 'EUR',
      original_amount: params.customsDutyEur,
      is_optional: false,
    },
    {
      step_number: 5,
      name_ru: 'Утилизационный сбор РФ (ПП РФ № 1713)',
      amount_rub: params.utilFeeRub,
      original_currency: null,
      original_amount: null,
      is_optional: false,
    },
    {
      step_number: 6,
      name_ru: 'СВХ, таможенный брокер, СБКТС и ЭПТС',
      amount_rub: params.brokerAndSvhRub,
      original_currency: null,
      original_amount: null,
      is_optional: false,
    },
    {
      step_number: 7,
      name_ru: 'Смета кузовного ремонта Farpost',
      amount_rub: params.includeRepairs ? params.repairRub : 0,
      original_currency: null,
      original_amount: null,
      is_optional: true,
    },
  ]
}

export function deriveVerdict(params: {
  netBenefitRub: number
  benefitPct: number
  riskFlags: RiskFlags
  hasCriticalAnomaly: boolean
  metiRisk: boolean
  isCommercialUtil: boolean
  baseBodySummary: string
  baseInteriorSummary: string
  baseBullets: string[]
}): TrafficLightVerdict {
  const hasStopFactor =
    params.hasCriticalAnomaly ||
    params.riskFlags.is_flooded ||
    params.riskFlags.airbag_deployed ||
    params.riskFlags.pillar_or_frame_repair ||
    params.riskFlags.repaired_grade_r_ra ||
    params.riskFlags.odometer_issue

  let verdict: TrafficLightColor = 'yellow'
  let headline = 'ПОД ВОПРОСОМ — НУЖНА ПРОВЕРКА'

  if (hasStopFactor || params.netBenefitRub < 50_000) {
    verdict = 'red'
    headline = hasStopFactor
      ? 'ВЫСОКИЙ РИСК — ПОКУПКА НЕ РЕКОМЕНДОВАНА'
      : 'НИЗКАЯ ВЫГОДА — СТАВКА НЕВЫГОДНА'
  } else if (
    params.netBenefitRub >= 150_000 &&
    !params.riskFlags.underbody_rust &&
    !params.isCommercialUtil
  ) {
    verdict = 'green'
    headline = 'РЕКОМЕНДОВАНО К ПОКУПКЕ'
  } else if (params.netBenefitRub >= 150_000) {
    verdict = 'yellow'
    headline = 'ПОД ВОПРОСОМ — УЧТИТЕ НЮАНСЫ'
  } else {
    verdict = 'yellow'
    headline = 'СДЕРЖАННАЯ ВЫГОДА — СЛЕДИТЕ ЗА СТАВКОЙ'
  }

  const badgeText = formatVerdictBadgeText(params.netBenefitRub)

  const shortPrefix =
    verdict === 'green' ? 'Можно брать' : verdict === 'yellow' ? 'Под вопросом' : 'Высокий риск'

  const bullets = [...params.baseBullets]
  if (params.metiRisk && !bullets.some((item) => item.includes('METI'))) {
    bullets.push('Автомобиль попадает под ограничения METI — нужна транзитная логистика')
  }
  if (params.isCommercialUtil) {
    bullets.push('В расчёт заложен коммерческий утильсбор (ПП РФ № 1255)')
  }

  return {
    verdict,
    headline,
    short_verdict_label: `${shortPrefix} • ${formatRub(params.netBenefitRub, { signed: true })}`,
    badge_text: badgeText,
    net_benefit_rub: params.netBenefitRub,
    benefit_percentage: Number(params.benefitPct.toFixed(1)),
    body_summary_ru: params.baseBodySummary,
    interior_summary_ru: params.baseInteriorSummary,
    reasoning_bullets: bullets,
  }
}

export function recalculateMockLotDetail(
  base: LotDetailResponse,
  payload: RecalculateRequest,
): RecalculateResponse {
  const rawRate = base.economics.customs.rates_snapshot.jpy_rub_bank
  const rate = Number.isFinite(rawRate) && rawRate > 0 ? rawRate : JPY_RUB_RATE
  const hasValidBidJpy =
    typeof payload.bid_jpy === 'number' && Number.isFinite(payload.bid_jpy) && payload.bid_jpy > 0
  const hasValidBidRub =
    typeof payload.bid_rub === 'number' && Number.isFinite(payload.bid_rub) && payload.bid_rub > 0

  const appliedBidJpy = hasValidBidJpy
    ? Math.round(payload.bid_jpy!)
    : hasValidBidRub
      ? Math.round(payload.bid_rub! / rate)
      : base.economics.wise_cost_ladder.car_bid_jpy

  const appliedBidRub = hasValidBidRub
    ? Math.round(payload.bid_rub!)
    : Math.round(appliedBidJpy * rate)

  const isCommercialUtil =
    typeof payload.is_commercial_util === 'boolean'
      ? payload.is_commercial_util
      : base.economics.customs.is_commercial_util

  const includeRepairs =
    typeof payload.include_repairs === 'boolean'
      ? payload.include_repairs
      : base.economics.is_repairs_included

  const utilFeeRub = isCommercialUtil ? COMMERCIAL_UTIL_FEE_RUB : PERSONAL_UTIL_FEE_RUB
  const freightRub = payload.custom_freight_rub ?? base.economics.customs.freight_vladivostok_rub
  const japanFeeStep = base.economics.wise_cost_ladder.steps.find((s) => s.step_number === 2)
  const japanFeeJpy = japanFeeStep?.original_amount ?? 85_000
  const japanFeeRub = japanFeeStep?.amount_rub ?? Math.round(japanFeeJpy * rate)
  const customsDutyEur = base.economics.customs.customs_duty_eur
  const customsDutyRub = base.economics.customs.customs_duty_rub
  const brokerAndSvhRub = base.economics.customs.broker_svh_sbkts_rub
  const repairRub = base.economics.farpost_repair.grand_total_repair_rub

  const updatedSteps = buildWiseSteps({
    bidJpy: appliedBidJpy,
    bidRub: appliedBidRub,
    japanFeeJpy,
    japanFeeRub,
    freightRub,
    customsDutyEur,
    customsDutyRub,
    utilFeeRub,
    brokerAndSvhRub,
    repairRub,
    includeRepairs,
  })

  const turnkeyCostRub = updatedSteps.reduce((acc, step) => acc + step.amount_rub, 0)
  const marketPriceRfRub = base.market.market_price_rf_rub
  const netBenefitRub = marketPriceRfRub - turnkeyCostRub
  const benefitPct = turnkeyCostRub > 0 ? (netBenefitRub / turnkeyCostRub) * 100 : 0

  const updatedCustoms: CustomsCalculation = {
    ...base.economics.customs,
    is_commercial_util: isCommercialUtil,
    utilization_fee_rub: utilFeeRub,
    freight_vladivostok_rub: freightRub,
  }

  const updatedVerdict = deriveVerdict({
    netBenefitRub,
    benefitPct,
    riskFlags: base.passport.risk_flags,
    hasCriticalAnomaly: base.audit.has_critical_anomaly,
    metiRisk: base.economics.customs.meti_sanction_risk,
    isCommercialUtil,
    baseBodySummary: base.verdict.body_summary_ru,
    baseInteriorSummary: base.verdict.interior_summary_ru,
    baseBullets: base.verdict.reasoning_bullets,
  })

  return {
    lot_id: base.lot_id,
    recalculated_at: new Date().toISOString(),
    applied_bid_jpy: appliedBidJpy,
    applied_bid_rub: appliedBidRub,
    is_commercial_util: isCommercialUtil,
    include_repairs: includeRepairs,
    customs: updatedCustoms,
    wise_cost_ladder: {
      car_bid_jpy: appliedBidJpy,
      car_bid_rub: appliedBidRub,
      turnkey_cost_rub: turnkeyCostRub,
      market_price_rf_rub: marketPriceRfRub,
      net_benefit_rub: netBenefitRub,
      benefit_percentage: Number(benefitPct.toFixed(1)),
      steps: updatedSteps,
    },
    turnkey_cost_rub: turnkeyCostRub,
    market_price_rf_rub: marketPriceRfRub,
    net_benefit_rub: netBenefitRub,
    benefit_percentage: Number(benefitPct.toFixed(1)),
    verdict: updatedVerdict,
    pdf_report_stale: true,
  }
}
