import type { CostLadderStep, TtxItem } from '@/components/ui'
import type {
  ChecklistItemStatus,
  FuelType,
  LotDetailResponse,
  NormalizedSheet,
  OdometerStatus,
  RiskFlags,
  SafetyCheckItem,
  TrafficLightColor,
  WiseCostStep,
} from '@/types/api'
import { formatEngineLiters, formatJpy, formatMileageKm, formatRub } from '@/utils/formatters'

export const DEFAULT_JPY_RUB_RATE = 0.64
export const FX_RATE_SOURCE_LABEL = 'VL.ru Деньги'

export const MIN_BID_JPY = 100_000
export const MAX_BID_JPY = 50_000_000
export const MIN_BID_RUB = 50_000
export const MAX_BID_RUB = 50_000_000

export const NET_BENEFIT_SUCCESS_THRESHOLD_RUB = 150_000
export const NET_BENEFIT_WARNING_THRESHOLD_RUB = 50_000

export function resolveSafeJpyRate(rate: number | null | undefined): number {
  if (typeof rate === 'number' && Number.isFinite(rate) && rate > 0) {
    return rate
  }
  return DEFAULT_JPY_RUB_RATE
}

export function parsePositiveIntegerInput(raw: string): number | null {
  const digits = raw.replace(/[^\d]/g, '')
  if (!digits) return null
  const parsed = Number(digits)
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : null
}

export function clampBidJpy(value: number): number {
  if (!Number.isFinite(value)) return MIN_BID_JPY
  return Math.min(MAX_BID_JPY, Math.max(MIN_BID_JPY, Math.round(value)))
}

export function clampBidRub(value: number): number {
  if (!Number.isFinite(value)) return MIN_BID_RUB
  return Math.min(MAX_BID_RUB, Math.max(MIN_BID_RUB, Math.round(value)))
}

export interface ActiveRiskChip {
  label: string
  variant: 'danger' | 'warning' | 'info'
}

export function buildActiveRiskLabels(flags: RiskFlags): ActiveRiskChip[] {
  const chips: ActiveRiskChip[] = []
  if (flags.repaired_grade_r_ra) chips.push({ label: 'Аварийная оценка R/RA', variant: 'danger' })
  if (flags.pillar_or_frame_repair) chips.push({ label: 'Ремонт стоек/каркаса', variant: 'danger' })
  if (flags.core_support_repair) chips.push({ label: 'Ремонт рамки радиатора', variant: 'danger' })
  if (flags.odometer_issue) chips.push({ label: 'Нестыковка одометра', variant: 'danger' })
  if (flags.is_flooded) chips.push({ label: 'Риск затопления', variant: 'danger' })
  if (flags.airbag_deployed) chips.push({ label: 'Срабатывали SRS', variant: 'danger' })
  if (flags.underbody_rust) chips.push({ label: 'Налёт ржавчины S1–S2', variant: 'warning' })
  if (flags.windshield_damage) chips.push({ label: 'Дефект лобового стекла', variant: 'warning' })
  if (flags.panel_replaced_xx) chips.push({ label: 'Есть заменённые панели XX', variant: 'info' })
  return chips
}

export const VERDICT_META: Record<
  TrafficLightColor,
  {
    badgeVariant: 'success' | 'warning' | 'danger'
    label: string
    shortTitle: string
  }
> = {
  green: {
    badgeVariant: 'success',
    label: 'Можно брать',
    shortTitle: 'Рекомендуется к покупке',
  },
  yellow: {
    badgeVariant: 'warning',
    label: 'Под вопросом',
    shortTitle: 'Требует проверки сметы и рисков',
  },
  red: {
    badgeVariant: 'danger',
    label: 'Высокий риск',
    shortTitle: 'Покупка не рекомендуется',
  },
}

export const CHECKLIST_STATUS_META: Record<
  ChecklistItemStatus,
  { variant: 'neutral' | 'success' | 'warning' | 'danger'; label: string; squircleColor: string }
> = {
  ok: { variant: 'success', label: 'Норма', squircleColor: '#34C759' },
  warning: { variant: 'warning', label: 'Риск', squircleColor: '#FF9500' },
  critical: { variant: 'danger', label: 'Критично', squircleColor: '#FF3B30' },
  unknown: { variant: 'neutral', label: 'Нет данных', squircleColor: '#8E8E93' },
}

export const SAFETY_SHORT_LABELS: Record<SafetyCheckItem['system_key'], string> = {
  structural_frame: 'Каркас и лонжероны',
  airbags_srs: 'Подушки SRS',
  engine_transmission: 'Двигатель и КПП',
  underbody_corrosion: 'Днище и коррозия',
  flood_or_fire: 'Признаки затопления / градобоя',
}

const ODOMETER_LABELS_RU: Record<OdometerStatus, string> = {
  confirmed: 'подтверждён',
  replaced: 'заменён (*)',
  tampered: 'скручен ($)',
  unknown: 'не подтверждён (#)',
}

const FUEL_LABELS_RU: Record<FuelType, string> = {
  gasoline: 'Бензин',
  hybrid: 'Гибрид',
  diesel: 'Дизель',
  ev: 'Электро',
  other: 'Другое',
}

export function formatLotSpecsSubtitle(
  passport: Pick<
    NormalizedSheet,
    'first_reg_year' | 'engine_cc' | 'mileage_km' | 'auction_house' | 'lot_number'
  >,
): string {
  return [
    passport.first_reg_year ?? '—',
    formatEngineLiters(passport.engine_cc),
    formatMileageKm(passport.mileage_km),
    `${passport.auction_house} #${passport.lot_number}`,
  ].join(' · ')
}

export function formatSpreadLabel(netBenefitRub: number, options?: { signed?: boolean }): string {
  const absRub = Math.abs(netBenefitRub)
  if (netBenefitRub < 0) {
    return `Переплата: ${formatRub(absRub)}`
  }
  return `Выгода: ${formatRub(absRub, { signed: options?.signed })}`
}

export function formatRoiPercent(
  benefitPercentage: number,
  options?: { fixedDigits?: number },
): string {
  const formatted =
    typeof options?.fixedDigits === 'number'
      ? benefitPercentage.toFixed(options.fixedDigits)
      : String(benefitPercentage)
  return `${benefitPercentage > 0 ? '+' : ''}${formatted}%`
}

export function formatDromPriceRange(minRub: number | null, maxRub: number | null): string | null {
  if (!minRub || !maxRub) return null
  return `${formatRub(minRub)} – ${formatRub(maxRub)}`
}

export function formatUtilModeLabel(
  isCommercialUtil: boolean,
  isUnder160Hp: boolean | null,
  variant: 'short' | 'detailed' = 'short',
): string {
  if (variant === 'detailed') {
    if (isCommercialUtil) {
      return 'Коммерческий тариф по ПП РФ № 1255 (для перепродажи / юрлица)'
    }
    if (isUnder160Hp === false) {
      return 'Мощность > 160 л.с. — применяется повышенный утильсбор'
    }
    return 'Льготный личный ввоз для физлица (≤ 160 л.с.): 5 200 ₽'
  }

  if (isCommercialUtil) return 'Коммерческий тариф (ПП РФ № 1255)'
  if (isUnder160Hp === false) return 'Повышенный тариф (> 160 л.с.)'
  return 'Льготный для физлица (≤ 160 л.с.)'
}

export function getBenefitBadgeVariant(netBenefitRub: number): 'success' | 'warning' | 'danger' {
  if (netBenefitRub >= NET_BENEFIT_SUCCESS_THRESHOLD_RUB) return 'success'
  if (netBenefitRub >= NET_BENEFIT_WARNING_THRESHOLD_RUB) return 'warning'
  return 'danger'
}

export function buildLotTtxItems(
  detail: LotDetailResponse,
  options?: { katashikiSpan?: 1 | 2 },
): TtxItem[] {
  const { passport, audit } = detail
  const engineStr = passport.engine_cc ? `${passport.engine_cc.toLocaleString('ru-RU')} см³` : '—'
  const hpNote =
    passport.is_under_160_hp === true
      ? ' (≤ 160)'
      : passport.is_under_160_hp === false
        ? ' (> 160)'
        : ''
  const powerStr = passport.power_hp ? `${passport.power_hp} л.с.${hpNote}` : 'не указана'

  const mileageValue =
    passport.mileage_km !== null
      ? `${formatMileageKm(passport.mileage_km)} · ${ODOMETER_LABELS_RU[passport.odometer_status]}`
      : '—'

  const drivePart = passport.drive_type ? ` · ${passport.drive_type}` : ''
  const fuelPart = passport.fuel_type ? ` · ${FUEL_LABELS_RU[passport.fuel_type]}` : ''
  const colorValue = passport.color_ru
    ? passport.paint_code
      ? `${passport.color_ru} (${passport.paint_code})`
      : passport.color_ru
    : (passport.paint_code ?? '—')

  const gradesValue = [
    `Общая ${passport.overall_grade}`,
    passport.exterior_grade ? `Кузов ${passport.exterior_grade}` : null,
    passport.interior_grade ? `Салон ${passport.interior_grade}` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  const auctionTitle = passport.auction_branch || passport.auction_house

  return [
    { label: 'Номер кузова (Frame ID)', value: passport.frame_id },
    {
      label: 'Регистрация и коридор ЕАЭС',
      value: passport.first_reg_date_str || String(passport.first_reg_year ?? '—'),
    },
    {
      label: 'Двигатель и мощность',
      value: `${formatEngineLiters(passport.engine_cc)} (${engineStr}) · ${powerStr}`,
    },
    { label: 'Пробег и одометр', value: mileageValue },
    { label: 'КПП и привод', value: `${passport.transmission}${drivePart}${fuelPart}` },
    { label: 'Цвет и код краски', value: colorValue },
    { label: 'Оценки аукциона', value: gradesValue },
    {
      label: 'Площадка и строгость',
      value: `${auctionTitle} (${passport.auction_strictness_index.toFixed(2)})`,
    },
    {
      label: 'Код модели (Katashiki)',
      value: `${passport.model_code} · торгов в архиве: ${audit.times_auctioned}`,
      span: options?.katashikiSpan ?? 2,
    },
  ]
}

export function formatLadderStepHint(
  stepNumber: number,
  currency: string | null,
  original: number | null,
  bidJpy: number,
  jpyRate: number,
): string | undefined {
  if (stepNumber === 1) {
    return `${formatJpy(bidJpy)} · курс ${jpyRate.toFixed(3)} ₽`
  }
  if (!currency || original === null) return undefined
  if (currency === 'EUR') {
    return `${original.toFixed(2)} EUR`
  }
  return `${Math.round(original).toLocaleString('ru-RU')} ${currency}`
}

export interface BuildLadderStepsOptions {
  bidJpy: number
  jpyRate: number
  displayBidRub?: number
  isPreviewPending?: boolean
  includeRepairs?: boolean
}

export function buildCostLadderSteps(
  steps: WiseCostStep[],
  options: BuildLadderStepsOptions,
): CostLadderStep[] {
  return steps.map((step) => {
    const amountRub =
      step.step_number === 1 && options.displayBidRub !== undefined
        ? options.displayBidRub
        : step.amount_rub
    return {
      label: step.name_ru,
      value: formatRub(amountRub),
      hint: formatLadderStepHint(
        step.step_number,
        step.original_currency,
        step.original_amount,
        options.bidJpy,
        options.jpyRate,
      ),
      active:
        (step.step_number === 1 && Boolean(options.isPreviewPending)) ||
        (step.step_number === 7 && Boolean(options.includeRepairs) && amountRub > 0),
    }
  })
}
