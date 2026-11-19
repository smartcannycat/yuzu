import type { PresetDetailConfig } from '@/api/mock/lotDetailsPresets'
import { EUR_RUB_RATE, JPY_RUB_RATE, USD_RUB_RATE } from '@/api/mock/lotEconomicsCalc'
import type {
  ChecklistItemStatus,
  CrossAuditReport,
  CustomsCalculation,
  FarpostRepairSummary,
  LotSummary,
  NormalizedDefect,
  NormalizedSheet,
  RiskFlags,
  SafetyChecklist,
  SafetyCheckItem,
} from '@/types/api'

export const DEFAULT_RISK_FLAGS: RiskFlags = {
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

export function buildSafetyChecklist(riskFlags: RiskFlags): SafetyChecklist {
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

export function buildFarpostRepairSummary(
  summary: LotSummary,
  preset: PresetDetailConfig | undefined,
): FarpostRepairSummary {
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

  return {
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
}

export function buildMockCustoms(params: {
  engineCc: number
  dutyRateEurPerCc: number
  customsDutyEur: number
  customsDutyRub: number
  isUnder160: boolean
  isCommercialUtil: boolean
  utilFeeRub: number
  freightRub: number
  brokerAndSvhRub: number
  metiSanctionRisk: boolean
}): CustomsCalculation {
  return {
    age_corridor: '3_to_5_years',
    duty_calculation_mode: 'eur_per_cc',
    engine_cc: params.engineCc,
    duty_rate_eur_per_cc: params.dutyRateEurPerCc,
    effective_duty_pct: null,
    customs_duty_eur: params.customsDutyEur,
    customs_duty_rub: params.customsDutyRub,
    excise_rub: 0,
    import_vat_rub: 0,
    is_under_160_hp: params.isUnder160,
    is_commercial_util: params.isCommercialUtil,
    util_fee_type: params.isCommercialUtil ? 'commercial' : 'personal',
    utilization_fee_rub: params.utilFeeRub,
    customs_clearance_fee_rub: 4268,
    freight_vladivostok_rub: params.freightRub,
    broker_svh_sbkts_rub: params.brokerAndSvhRub,
    meti_sanction_risk: params.metiSanctionRisk,
    rates_snapshot: {
      jpy_rub_bank: JPY_RUB_RATE,
      jpy_rate_source: 'VL.ru Деньги',
      eur_rub_cbrf: EUR_RUB_RATE,
      usd_rub_cbrf: USD_RUB_RATE,
      cbrf_date: '13.11.2026',
    },
  }
}

export function buildMockCrossAudit(
  summary: LotSummary,
  passport: NormalizedSheet,
  defects: NormalizedDefect[],
  carBidJpy: number,
  preset: PresetDetailConfig | undefined,
): CrossAuditReport {
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

  return {
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
}
