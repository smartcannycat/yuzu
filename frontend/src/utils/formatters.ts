import type { TaskStep, TrafficLightColor } from '@/types/api'

const rubNumberFormatter = new Intl.NumberFormat('ru-RU')
const shortDateFormatter = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
})

const TASK_STEP_LABELS_RU: Record<TaskStep, string> = {
  gatekeeper: 'Проверка листа',
  fast_header_ocr: 'Распознавание шапки',
  gemini_ocr: 'Чтение схемы и заметок',
  cross_audit: 'Кросс-аудит аукционника',
  customs_calc: 'Расчёт пошлин и утильсбора',
  farpost_parts: 'Поиск кузовных запчастей',
  drom_market: 'Сравнение с ценами на Drom',
  scoring: 'Финальный скоринг',
  completed: 'Готово',
  failed: 'Ошибка анализа',
}

const VERDICT_LABELS_RU: Record<TrafficLightColor, string> = {
  green: 'Можно брать',
  yellow: 'Под вопросом',
  red: 'Высокий риск',
}

/**
 * Formats integer amounts in Russian rubles using non-breaking space grouping.
 */
export function formatRub(amount: number, options?: { signed?: boolean }): string {
  const rounded = Math.round(amount)
  const absFormatted = rubNumberFormatter.format(Math.abs(rounded))

  if (rounded < 0) {
    return `-${absFormatted} ₽`
  }

  if (options?.signed && rounded > 0) {
    return `+${absFormatted} ₽`
  }

  return `${absFormatted} ₽`
}

/**
 * Formats mileage in kilometers (e.g. "62 000 км") or returns an em-dash if unknown.
 */
export function formatMileageKm(mileageKm: number | null): string {
  if (mileageKm === null || Number.isNaN(mileageKm)) {
    return '—'
  }
  return `${rubNumberFormatter.format(Math.round(mileageKm))} км`
}

/**
 * Formats engine displacement in liters (e.g. 1797 -> "1.8 л") or falls back to em-dash.
 */
export function formatEngineLiters(engineCc: number | null): string {
  if (engineCc === null || engineCc <= 0 || Number.isNaN(engineCc)) {
    return '—'
  }
  return `${(engineCc / 1000).toFixed(1)} л`
}

/**
 * Maps internal pipeline step codes to user-facing Russian step names without percentages.
 */
export function formatTaskStepRu(step: TaskStep): string {
  return TASK_STEP_LABELS_RU[step]
}

/**
 * Maps traffic light verdict colors to short Russian labels.
 */
export function formatVerdictLabelRu(verdict: TrafficLightColor): string {
  return VERDICT_LABELS_RU[verdict]
}

/**
 * Formats ISO timestamps into compact Russian dates (e.g. "31 мая").
 */
export function formatShortDateRu(isoDate: string): string {
  const parsed = new Date(isoDate)
  if (Number.isNaN(parsed.getTime())) {
    return '—'
  }
  return shortDateFormatter.format(parsed)
}

/**
 * Strips leading traffic-light emoji glyphs or decorative bullets that backend strings may include.
 */
export function cleanVerdictText(headline: string): string {
  return headline.replace(/^[\p{Extended_Pictographic}\uFE0F\u200D\s]+/u, '').trim()
}

/**
 * Formats a count of vehicles with Russian pluralization (e.g. "1 автомобиль", "2 автомобиля").
 */
export function formatCarCountRu(count: number): string {
  const abs = Math.abs(Math.trunc(count))
  const mod100 = abs % 100
  const mod10 = abs % 10

  if (mod100 >= 11 && mod100 <= 14) {
    return `${abs} автомобилей`
  }
  if (mod10 === 1) {
    return `${abs} автомобиль`
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return `${abs} автомобиля`
  }
  return `${abs} автомобилей`
}
