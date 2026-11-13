import { PANEL_LABELS_RU, PRESET_CONFIGS } from '@/api/mock/lotDetailsPresets'
import {
  buildWiseSteps,
  COMMERCIAL_UTIL_FEE_RUB,
  EUR_RUB_RATE,
  formatVerdictBadgeText,
  JPY_RUB_RATE,
  PERSONAL_UTIL_FEE_RUB,
  recalculateMockLotDetail,
  USD_RUB_RATE,
} from '@/api/mock/lotEconomicsCalc'
import { buildMockSheetSvgDataUrl } from '@/api/mock/lotSheetSvg'
import type {
  ChecklistItemStatus,
  CrossAuditReport,
  CustomsCalculation,
  EconomicsDetail,
  FarpostRepairSummary,
  LotDetailResponse,
  LotSummary,
  NormalizedDefect,
  NormalizedSheet,
  RiskFlags,
  SafetyChecklist,
  SafetyCheckItem,
  TrafficLightVerdict,
} from '@/types/api'

export { recalculateMockLotDetail }

const DEFAULT_RISK_FLAGS: RiskFlags = {
  is_flooded: false,
  airbag_deployed: false,
  hail_damage: false,
  underbody_corrosion: false,
  pillar_or_frame_repair: false,
  core_support_repair: false,
  underbody_rust: false,
  panel_needs_replacement_x: false,
  panel_replaced_xx: false,
  odometer_issue: false,
  color_changed: false,
  windshield_damage: false,
  repaired_grade_r_ra: false,
}

function buildSafetyChecklist(riskFlags: RiskFlags): SafetyChecklist {
  const frameStatus: ChecklistItemStatus = riskFlags.pillar_or_frame_repair ? 'critical' : 'ok'
  const srsStatus: ChecklistItemStatus = riskFlags.airbag_deployed ? 'critical' : 'ok'
  const engineStatus: ChecklistItemStatus = riskFlags.odometer_issue ? 'critical' : 'ok'
  const corrosionStatus: ChecklistItemStatus = riskFlags.underbody_corrosion
    ? 'critical'
    : riskFlags.underbody_rust
      ? 'warning'
      : 'ok'
  const floodStatus: ChecklistItemStatus =
    riskFlags.is_flooded || riskFlags.hail_damage ? 'critical' : 'ok'

  const items: SafetyCheckItem[] = [
    {
      system_key: 'structural_frame',
      label_ru: 'Силовой каркас и лонжероны',
      status: frameStatus,
      detail_ru: riskFlags.pillar_or_frame_repair
        ? 'На листе выявлены следы ремонта несущих стоек или лонжеронов (оценка R/RA).'
        : 'Следов ремонта лонжеронов, стоек и пола багажника не выявлено.',
    },
    {
      system_key: 'airbags_srs',
      label_ru: 'Подушки безопасности (SRS)',
      status: srsStatus,
      detail_ru: riskFlags.airbag_deployed
        ? 'Зафиксировано срабатывание или демонтаж подушек безопасности.'
        : 'Замечаний по модулям SRS и индикаторам на приборной панели нет.',
    },
    {
      system_key: 'engine_transmission',
      label_ru: 'Двигатель, КПП и одометр',
      status: engineStatus,
      detail_ru: riskFlags.odometer_issue
        ? 'Обнаружена нестыковка пробега с архивными торгами или замена одометра.'
        : 'Пробег подтверждён, посторонних шумов и ошибок трансмиссии не отмечено.',
    },
    {
      system_key: 'underbody_corrosion',
      label_ru: 'Днище, пороги и коррозия',
      status: corrosionStatus,
      detail_ru: riskFlags.underbody_corrosion
        ? 'Глубокая/сквозная коррозия порогов и элементов рамы.'
        : riskFlags.underbody_rust
          ? 'Поверхностный налёт ржавчины S1/S2 — рекомендуется антикор во Владивостоке.'
          : 'Критичной коррозии силовых элементов и днища не обнаружено.',
    },
    {
      system_key: 'flood_or_fire',
      label_ru: 'Признаки затопления / градобоя',
      status: floodStatus,
      detail_ru: riskFlags.is_flooded
        ? 'На аукционном листе присутствуют отметки топляка (冠水車).'
        : 'Признаков подтопления салона, окисления проводки или градобоя нет.',
    },
  ]

  const hasCritical = items.some((item) => item.status === 'critical')
  const hasWarning = items.some((item) => item.status === 'warning')
  const overallStatus: ChecklistItemStatus = hasCritical
    ? 'critical'
    : hasWarning
      ? 'warning'
      : 'ok'
  const overallLabel = hasCritical ? 'Стоп-фактор' : hasWarning ? 'Есть замечания' : 'В норме'

  return {
    overall_status: overallStatus,
    overall_label_ru: overallLabel,
    items,
  }
}

export function buildMockLotDetail(summary: LotSummary): LotDetailResponse {
  const preset = PRESET_CONFIGS[summary.lot_id]
  const riskFlags: RiskFlags = {
    ...DEFAULT_RISK_FLAGS,
    repaired_grade_r_ra: summary.overall_grade === 'R' || summary.overall_grade === 'RA',
    ...preset?.riskFlagsOverride,
  }

  const partsTotal = preset
    ? preset.parts.reduce((acc, part) => acc + part.price_from_rub, 0)
    : summary.has_anomaly
      ? 15000
      : 0
  const worksTotal = preset
    ? preset.serviceWorks.reduce((acc, work) => acc + work.amount_rub, 0)
    : summary.has_anomaly
      ? 9000
      : 0
  const repairTotal = partsTotal + worksTotal

  const farpostRepair: FarpostRepairSummary = {
    parts: preset?.parts ?? [],
    service_works:
      preset?.serviceWorks ??
      (repairTotal > 0
        ? [
            {
              work_type: 'pdr_and_polish',
              label_ru: 'Предпродажная подготовка и устранение косметики',
              amount_rub: repairTotal,
              zero_cost_reason_ru: null,
            },
          ]
        : []),
    total_parts_from_rub: partsTotal,
    total_works_rub: worksTotal,
    grand_total_repair_rub: repairTotal,
    has_color_matched_parts: Boolean(preset?.serviceWorks.some((w) => w.amount_rub === 0)),
    included_in_turnkey_hint_ru: 'Сумма уже включена в расчёт под ключ во Владивостоке',
  }

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
  const rawBidRub = Math.max(220_000, summary.turnkey_cost_rub - fixedCostsRub)
  const carBidJpy = Math.max(300_000, Math.round(rawBidRub / JPY_RUB_RATE / 10_000) * 10_000)
  const carBidRub = Math.max(0, summary.turnkey_cost_rub - fixedCostsRub)

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

  const benefitPct =
    summary.turnkey_cost_rub > 0 ? (summary.net_benefit_rub / summary.turnkey_cost_rub) * 100 : 0

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
    badge_text: formatVerdictBadgeText(summary.net_benefit_rub),
    net_benefit_rub: summary.net_benefit_rub,
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

  const customs: CustomsCalculation = {
    age_corridor: '3_to_5_years',
    duty_calculation_mode: 'eur_per_cc',
    engine_cc: engineCc,
    duty_rate_eur_per_cc: dutyRateEurPerCc,
    effective_duty_pct: null,
    customs_duty_eur: customsDutyEur,
    customs_duty_rub: customsDutyRub,
    is_under_160_hp: isUnder160,
    is_commercial_util: isCommercialUtil,
    utilization_fee_rub: utilFeeRub,
    customs_clearance_fee_rub: 4268,
    freight_vladivostok_rub: freightRub,
    broker_svh_sbkts_rub: brokerAndSvhRub,
    meti_sanction_risk: summary.meti_sanction_risk,
    rates_snapshot: {
      jpy_rub_bank: JPY_RUB_RATE,
      jpy_rate_source: 'VL.ru Деньги',
      eur_rub_cbrf: EUR_RUB_RATE,
      usd_rub_cbrf: USD_RUB_RATE,
      cbrf_date: '13.11.2026',
    },
  }

  const economics: EconomicsDetail = {
    bid_slider_min_jpy: Math.max(200_000, Math.round((carBidJpy * 0.55) / 10_000) * 10_000),
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
      turnkey_cost_rub: summary.turnkey_cost_rub,
      market_price_rf_rub: summary.market_price_rf_rub,
      net_benefit_rub: summary.net_benefit_rub,
      benefit_percentage: Number(benefitPct.toFixed(1)),
      steps,
    },
  }

  const hasCriticalAnomaly = preset?.hasCriticalAnomaly ?? false
  const anomalies = preset?.anomalies ?? []
  const history = preset?.history ?? [
    {
      auction_date: '25.05.2026',
      auction_house: passport.auction_branch ?? summary.auction_house,
      auction_strictness: passport.auction_strictness_index,
      lot_number: summary.lot_number,
      overall_grade: summary.overall_grade,
      mileage_km: summary.mileage_km,
      defects_summary: defects.map((d) => `${d.raw_code} ${d.panel_ru}`).join(', '),
      closing_price_jpy: carBidJpy,
      sheet_archive_url: null,
    },
  ]

  const audit: CrossAuditReport = {
    status: hasCriticalAnomaly || anomalies.length > 0 ? 'anomaly_detected' : 'clean',
    source_name: 'AucJP + AAA Japan / Pravto',
    is_archive_available: true,
    risk_level: hasCriticalAnomaly ? 'CRITICAL' : anomalies.length > 0 ? 'WARNING' : 'CLEAN',
    has_critical_anomaly: hasCriticalAnomaly,
    headline_ru: hasCriticalAnomaly
      ? 'ВНИМАНИЕ: Выявлены расхождения пробега и следы силового ремонта в архиве торгов'
      : anomalies.length > 0
        ? 'Зафиксированы расхождения кузовных деталей относительно прошлых торгов'
        : 'Кросс-аудит чист — расхождений с историей японских аукционов не найдено',
    times_auctioned: history.length,
    verified_at: '2026-11-13T10:15:00Z',
    anomalies,
    history,
  }

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
