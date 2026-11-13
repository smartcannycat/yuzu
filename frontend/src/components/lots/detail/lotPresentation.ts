import type { CostLadderStep, TtxItem } from '@/components/ui'
import type {
  FuelType,
  LotDetailResponse,
  OdometerStatus,
  RiskFlags,
  TrafficLightColor,
  WiseCostStep,
} from '@/types/api'
import { formatEngineLiters, formatMileageKm, formatRub } from '@/utils/formatters'

export interface ActiveRiskChip {
  label: string
  variant: 'danger' | 'warning' | 'info'
}

export function buildActiveRiskLabels(flags: RiskFlags): ActiveRiskChip[] {
  const chips: ActiveRiskChip[] = []
  if (flags.repaired_grade_r_ra) chips.push({ label: 'Аварийная оценка R/RA', variant: 'danger' })
  if (flags.pillar_or_frame_repair) chips.push({ label: 'Ремонт стоек/каркаса', variant: 'danger' })
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
}

export function buildLotTtxItems(detail: LotDetailResponse): TtxItem[] {
  const { passport, audit } = detail
  const engineStr = passport.engine_cc ? `${passport.engine_cc.toLocaleString('ru-RU')} см³` : '—'
  const powerStr = passport.power_hp
    ? `${passport.power_hp} л.с.${passport.is_under_160_hp ? ' (≤ 160)' : ' (> 160)'}`
    : 'не указана'

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
      span: 2,
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
    return `${Math.round(bidJpy).toLocaleString('ru-RU')} ¥ · курс ${jpyRate.toFixed(3)} ₽`
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
