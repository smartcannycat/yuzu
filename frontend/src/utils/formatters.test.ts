import { describe, expect, it } from 'vitest'

import {
  cleanVerdictText,
  formatArchiveBadgeLabelRu,
  formatCarCountRu,
  formatCardDateLabel,
  formatEngineLiters,
  formatJpy,
  formatMileageKm,
  formatRub,
  formatSheetCountRu,
  formatShortDateRu,
  formatTaskStepRu,
  formatVerdictLabelRu,
} from './formatters'
import { TRAFFIC_LIGHT_META } from './lotPresentation'

describe('formatters', () => {
  it('formats positive, negative, signed, and non-finite ruble amounts cleanly', () => {
    expect(formatRub(1540000)).toMatch(/^1\s540\s000 ₽$/)
    expect(formatRub(280000, { signed: true })).toMatch(/^\+280\s000 ₽$/)
    expect(formatRub(-95000, { signed: true })).toMatch(/^-95\s000 ₽$/)
    expect(formatRub(0, { signed: true })).toBe('0 ₽')
    expect(formatRub(Number.NaN)).toBe('—')
    expect(formatRub(Number.POSITIVE_INFINITY)).toBe('—')
    expect(formatRub(Number.NEGATIVE_INFINITY)).toBe('—')
  })

  it('formats yen amounts and falls back on non-finite numbers', () => {
    expect(formatJpy(1450000)).toMatch(/^1\s450\s000 ¥$/)
    expect(formatJpy(Number.NaN)).toBe('—')
    expect(formatJpy(Number.POSITIVE_INFINITY)).toBe('—')
  })

  it('formats mileage and handles null and non-finite values gracefully', () => {
    expect(formatMileageKm(62000)).toMatch(/^62\s000 км$/)
    expect(formatMileageKm(null)).toBe('—')
    expect(formatMileageKm(Number.NaN)).toBe('—')
    expect(formatMileageKm(Number.POSITIVE_INFINITY)).toBe('—')
  })

  it('formats engine displacement in liters and guards non-finite values', () => {
    expect(formatEngineLiters(1797)).toBe('1.8 л')
    expect(formatEngineLiters(1496)).toBe('1.5 л')
    expect(formatEngineLiters(null)).toBe('—')
    expect(formatEngineLiters(0)).toBe('—')
    expect(formatEngineLiters(Number.NaN)).toBe('—')
    expect(formatEngineLiters(Number.POSITIVE_INFINITY)).toBe('—')
  })

  it('maps task step enums and verdicts to canonical Russian labels', () => {
    expect(formatTaskStepRu('customs_calc')).toBe('Расчёт пошлин и утильсбора')
    expect(formatTaskStepRu('drom_market')).toBe('Сравнение с ценами на Drom')
    expect(formatVerdictLabelRu('green')).toBe(TRAFFIC_LIGHT_META.green.label)
    expect(formatVerdictLabelRu('yellow')).toBe(TRAFFIC_LIGHT_META.yellow.label)
    expect(formatVerdictLabelRu('red')).toBe(TRAFFIC_LIGHT_META.red.label)
  })

  it('formats valid ISO dates and falls back on invalid timestamps', () => {
    expect(formatShortDateRu('2026-05-31T10:25:00Z')).not.toBe('—')
    expect(formatShortDateRu('invalid-date')).toBe('—')
  })

  it('trims plain-text verdict headlines cleanly', () => {
    expect(cleanVerdictText('  Можно брать • +280к выгода  ')).toBe('Можно брать • +280к выгода')
  })

  it('pluralizes Russian car and sheet counts accurately', () => {
    expect(formatCarCountRu(1)).toBe('1 автомобиль')
    expect(formatCarCountRu(2)).toBe('2 автомобиля')
    expect(formatCarCountRu(5)).toBe('5 автомобилей')
    expect(formatCarCountRu(11)).toBe('11 автомобилей')
    expect(formatCarCountRu(22)).toBe('22 автомобиля')
    expect(formatCarCountRu(Number.NaN)).toBe('0 автомобилей')

    expect(formatSheetCountRu(1)).toBe('1 лист')
    expect(formatSheetCountRu(3)).toBe('3 листа')
    expect(formatSheetCountRu(5)).toBe('5 листов')
    expect(formatSheetCountRu(11)).toBe('11 листов')
    expect(formatSheetCountRu(21)).toBe('21 лист')
  })

  it('formats card auction date labels and archive status badges', () => {
    expect(formatCardDateLabel('14.11.2026', '2026-11-10T10:00:00Z')).toBe('Торги 14.11')
    expect(formatCardDateLabel(null, '2026-05-31T10:25:00Z')).toBe(
      formatShortDateRu('2026-05-31T10:25:00Z'),
    )
    expect(formatCardDateLabel('invalid', '2026-05-31T10:25:00Z')).toBe(
      formatShortDateRu('2026-05-31T10:25:00Z'),
    )

    expect(formatArchiveBadgeLabelRu(false, null)).toBeNull()
    expect(formatArchiveBadgeLabelRu(true, 'expired')).toBe('Торги прошли')
    expect(formatArchiveBadgeLabelRu(true, 'manual')).toBe('В архиве')
    expect(formatArchiveBadgeLabelRu(true, null)).toBe('В архиве')
  })
})
