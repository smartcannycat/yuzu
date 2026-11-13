import { describe, expect, it } from 'vitest'

import {
  DEFAULT_JPY_RUB_RATE,
  MAX_BID_JPY,
  MAX_BID_RUB,
  MIN_BID_JPY,
  MIN_BID_RUB,
  clampBidJpy,
  clampBidRub,
  formatDromPriceRange,
  formatRoiPercent,
  formatSpreadLabel,
  formatUtilModeLabel,
  getBenefitBadgeVariant,
  parsePositiveIntegerInput,
  resolveSafeJpyRate,
} from '@/components/lots/detail/lotPresentation'

describe('lotPresentation helpers', () => {
  it('resolves safe JPY/RUB rate and falls back on non-positive or non-finite values', () => {
    expect(resolveSafeJpyRate(0.642)).toBe(0.642)
    expect(resolveSafeJpyRate(0)).toBe(DEFAULT_JPY_RUB_RATE)
    expect(resolveSafeJpyRate(-0.5)).toBe(DEFAULT_JPY_RUB_RATE)
    expect(resolveSafeJpyRate(Number.NaN)).toBe(DEFAULT_JPY_RUB_RATE)
    expect(resolveSafeJpyRate(Number.POSITIVE_INFINITY)).toBe(DEFAULT_JPY_RUB_RATE)
    expect(resolveSafeJpyRate(null)).toBe(DEFAULT_JPY_RUB_RATE)
  })

  it('parses and clamps numeric JPY and RUB bid inputs', () => {
    expect(parsePositiveIntegerInput('1 450 000 ¥')).toBe(1_450_000)
    expect(parsePositiveIntegerInput('0')).toBeNull()
    expect(parsePositiveIntegerInput('abc')).toBeNull()

    expect(clampBidJpy(500)).toBe(MIN_BID_JPY)
    expect(clampBidJpy(99_999_999)).toBe(MAX_BID_JPY)
    expect(clampBidJpy(Number.NaN)).toBe(MIN_BID_JPY)

    expect(clampBidRub(1_000)).toBe(MIN_BID_RUB)
    expect(clampBidRub(99_999_999)).toBe(MAX_BID_RUB)
    expect(clampBidRub(Number.POSITIVE_INFINITY)).toBe(MIN_BID_RUB)
  })

  it('formats spread, ROI, Drom range, utilization mode, and benefit badge variants', () => {
    expect(formatSpreadLabel(120_000)).toBe('Выгода: 120\u00A0000 ₽')
    expect(formatSpreadLabel(120_000, { signed: true })).toBe('Выгода: +120\u00A0000 ₽')
    expect(formatSpreadLabel(-45_000)).toBe('Переплата: 45\u00A0000 ₽')

    expect(formatRoiPercent(12.34, { fixedDigits: 1 })).toBe('+12.3%')
    expect(formatRoiPercent(-4.2, { fixedDigits: 1 })).toBe('-4.2%')
    expect(formatRoiPercent(0)).toBe('0%')

    expect(formatDromPriceRange(1_500_000, 1_900_000)).toBe(
      '1\u00A0500\u00A0000 ₽ – 1\u00A0900\u00A0000 ₽',
    )
    expect(formatDromPriceRange(null, 1_900_000)).toBeNull()

    expect(formatUtilModeLabel(true, true)).toBe('Коммерческий тариф (ПП РФ № 1255)')
    expect(formatUtilModeLabel(false, false)).toBe('Повышенный тариф (> 160 л.с.)')
    expect(formatUtilModeLabel(false, true)).toBe('Льготный для физлица (≤ 160 л.с.)')

    expect(getBenefitBadgeVariant(150_000)).toBe('success')
    expect(getBenefitBadgeVariant(50_000)).toBe('warning')
    expect(getBenefitBadgeVariant(49_999)).toBe('danger')
  })
})
