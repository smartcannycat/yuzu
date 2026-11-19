import {
  formatDromPriceRange,
  formatRoiPercent,
  formatSpreadLabel,
  formatUtilModeLabel,
} from '@/components/lots/detail/lotPresentation'
import type { LotDetailResponse } from '@/types/api'
import { formatRub } from '@/utils/formatters'

const RISKY_AUCTION_GRADES = new Set(['R', 'RA', '***'])

export function isRiskyAuctionGrade(grade: string | null | undefined): boolean {
  if (!grade) return false
  return RISKY_AUCTION_GRADES.has(grade.trim().toUpperCase())
}

export function formatRepairSummaryValue(
  isRepairsIncluded: boolean,
  grandTotalRepairRub: number,
): string {
  return isRepairsIncluded ? formatRub(grandTotalRepairRub) : 'Исключён (0 ₽)'
}

export interface LotFinancialSummaryView {
  turnkeyCostRub: number
  turnkeyFormatted: string
  marketLabel: string
  marketPriceFormatted: string
  dromRangeLabel: string
  dromRangeText: string | null
  repairFormatted: string
  netBenefitRub: number
  isOverpay: boolean
  spreadLabel: string
  roiFormatted: string
  utilModeLabel: string
}

/**
 * Shared summary presenter consumed by both the interactive General summary card
 * and Page 1 of the printable PDF report.
 */
export function buildLotFinancialSummary(
  detail: LotDetailResponse,
  options?: { roiFixedDigits?: number },
): LotFinancialSummaryView {
  const turnkeyCostRub = detail.economics.wise_cost_ladder.turnkey_cost_rub
  const netBenefitRub = detail.economics.wise_cost_ladder.net_benefit_rub
  const benefitPercentage =
    typeof options?.roiFixedDigits === 'number'
      ? detail.economics.wise_cost_ladder.benefit_percentage
      : detail.verdict.benefit_percentage

  const dromRangeText = formatDromPriceRange(
    detail.market.price_min_rub,
    detail.market.price_max_rub,
  )
  const { is_commercial_util: isCommercialUtil, is_under_160_hp: isUnder160Hp } =
    detail.economics.customs

  return {
    turnkeyCostRub,
    turnkeyFormatted: formatRub(turnkeyCostRub),
    marketLabel: `Рынок РФ (Drom · ${detail.market.analogs_count} авто)`,
    marketPriceFormatted: formatRub(detail.market.market_price_rf_rub),
    dromRangeLabel: `Разброс в наличии (${detail.market.search_region_ru})`,
    dromRangeText,
    repairFormatted: formatRepairSummaryValue(
      detail.economics.is_repairs_included,
      detail.economics.farpost_repair.grand_total_repair_rub,
    ),
    netBenefitRub,
    isOverpay: netBenefitRub < 0,
    spreadLabel: formatSpreadLabel(netBenefitRub),
    roiFormatted: formatRoiPercent(benefitPercentage, { fixedDigits: options?.roiFixedDigits }),
    utilModeLabel: formatUtilModeLabel(isCommercialUtil, isUnder160Hp, 'short'),
  }
}
