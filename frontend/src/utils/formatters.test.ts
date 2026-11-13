import { describe, expect, it } from 'vitest'

import {
  cleanVerdictText,
  formatCarCountRu,
  formatEngineLiters,
  formatMileageKm,
  formatRub,
  formatSheetCountRu,
  formatShortDateRu,
  formatTaskStepRu,
  formatVerdictLabelRu,
} from './formatters'

describe('formatters', () => {
  it('formats positive, negative, and signed ruble amounts cleanly', () => {
    expect(formatRub(1540000)).toMatch(/^1\s540\s000 ₽$/)
    expect(formatRub(280000, { signed: true })).toMatch(/^\+280\s000 ₽$/)
    expect(formatRub(-95000, { signed: true })).toMatch(/^-95\s000 ₽$/)
    expect(formatRub(0, { signed: true })).toBe('0 ₽')
  })

  it('formats mileage and handles null values gracefully', () => {
    expect(formatMileageKm(62000)).toMatch(/^62\s000 км$/)
    expect(formatMileageKm(null)).toBe('—')
  })

  it('formats engine displacement in liters', () => {
    expect(formatEngineLiters(1797)).toBe('1.8 л')
    expect(formatEngineLiters(1496)).toBe('1.5 л')
    expect(formatEngineLiters(null)).toBe('—')
    expect(formatEngineLiters(0)).toBe('—')
  })

  it('maps task step enums and verdicts to Russian labels without percentages', () => {
    expect(formatTaskStepRu('customs_calc')).toBe('Расчёт пошлин и утильсбора')
    expect(formatTaskStepRu('drom_market')).toBe('Сравнение с ценами на Drom')
    expect(formatVerdictLabelRu('green')).toBe('Можно брать')
    expect(formatVerdictLabelRu('yellow')).toBe('Под вопросом')
    expect(formatVerdictLabelRu('red')).toBe('Высокий риск')
  })

  it('formats valid ISO dates and falls back on invalid timestamps', () => {
    expect(formatShortDateRu('2026-05-31T10:25:00Z')).not.toBe('—')
    expect(formatShortDateRu('invalid-date')).toBe('—')
  })

  it('strips leading emoji markers from backend verdict headlines', () => {
    expect(cleanVerdictText('🟢 Можно брать • +280к выгода')).toBe('Можно брать • +280к выгода')
    expect(cleanVerdictText('Можно брать • +280к выгода')).toBe('Можно брать • +280к выгода')
  })

  it('pluralizes Russian car and sheet counts accurately', () => {
    expect(formatCarCountRu(1)).toBe('1 автомобиль')
    expect(formatCarCountRu(2)).toBe('2 автомобиля')
    expect(formatCarCountRu(5)).toBe('5 автомобилей')
    expect(formatCarCountRu(11)).toBe('11 автомобилей')
    expect(formatCarCountRu(22)).toBe('22 автомобиля')

    expect(formatSheetCountRu(1)).toBe('1 лист')
    expect(formatSheetCountRu(3)).toBe('3 листа')
    expect(formatSheetCountRu(5)).toBe('5 листов')
    expect(formatSheetCountRu(11)).toBe('11 листов')
    expect(formatSheetCountRu(21)).toBe('21 лист')
  })
})
