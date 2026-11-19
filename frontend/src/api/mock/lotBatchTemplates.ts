import { computeLotExpiresAt, formatJstAuctionDateWithOffset } from '@/api/mock/lotLifecycle'
import type { LotSummary } from '@/types/api'

export interface JdmTemplateSeed {
  keywords: readonly string[]
  make: string
  model: string
  year: number
  engine_cc: number
  framePrefix: string
  auction_house: LotSummary['auction_house']
  lot_number: string
  overall_grade: string
  mileage_km: number
  turnkey_cost_rub: number
  market_price_rf_rub: number
  verdict: LotSummary['verdict']
  verdict_headline: string
  net_benefit_rub: number
  meti_sanction_risk: boolean
  has_anomaly: boolean
  anomaly_text: string | null
}

export interface MockBatchItemRecord {
  lotId: string
  fileIndex: number
  originalFilename: string
  initialPreviewTitle?: string
  enqueuedAtMs: number
  startDelayMs: number
  initialStepIndex: number
  template: LotSummary
}

export interface MockBatchRecord {
  batchId: string
  createdAtIso: string
  items: MockBatchItemRecord[]
}

export const JDM_TEMPLATES: readonly JdmTemplateSeed[] = [
  {
    keywords: ['corolla', 'touring', '3142'],
    make: 'Toyota',
    model: 'Corolla Touring',
    year: 2021,
    engine_cc: 1797,
    framePrefix: 'ZWE211',
    auction_house: 'TAA',
    lot_number: '3142',
    overall_grade: '4',
    mileage_km: 54000,
    turnkey_cost_rub: 1580000,
    market_price_rf_rub: 1860000,
    verdict: 'green',
    verdict_headline: 'Можно брать • +280 000 ₽ к рынку РФ',
    net_benefit_rub: 280000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['harrier', '5541'],
    make: 'Toyota',
    model: 'Harrier',
    year: 2020,
    engine_cc: 1986,
    framePrefix: 'MXUA80',
    auction_house: 'USS',
    lot_number: '5541',
    overall_grade: '3.5',
    mileage_km: 71000,
    turnkey_cost_rub: 2540000,
    market_price_rf_rub: 2635000,
    verdict: 'yellow',
    verdict_headline: 'Под вопросом • окрас правой двери и ДВС >1.9 л',
    net_benefit_rub: 95000,
    meti_sanction_risk: true,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['vezel', '8412'],
    make: 'Honda',
    model: 'Vezel',
    year: 2021,
    engine_cc: 1496,
    framePrefix: 'RV5',
    auction_house: 'CAA',
    lot_number: '8412',
    overall_grade: '4.5',
    mileage_km: 39000,
    turnkey_cost_rub: 1910000,
    market_price_rf_rub: 2180000,
    verdict: 'green',
    verdict_headline: 'Можно брать • +270 000 ₽ и без санкций METI',
    net_benefit_rub: 270000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['note', '1102'],
    make: 'Nissan',
    model: 'Note e-Power',
    year: 2022,
    engine_cc: 1198,
    framePrefix: 'E13',
    auction_house: 'JU',
    lot_number: '1102',
    overall_grade: '4',
    mileage_km: 47000,
    turnkey_cost_rub: 1320000,
    market_price_rf_rub: 1495000,
    verdict: 'green',
    verdict_headline: 'Можно брать • чистый лист без окрасов',
    net_benefit_rub: 175000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['forester', '5190', 'subaru'],
    make: 'Subaru',
    model: 'Forester',
    year: 2019,
    engine_cc: 2498,
    framePrefix: 'SK9',
    auction_house: 'TAA',
    lot_number: '5190',
    overall_grade: 'R',
    mileage_km: 92000,
    turnkey_cost_rub: 2480000,
    market_price_rf_rub: 2390000,
    verdict: 'red',
    verdict_headline: 'Высокий риск • замена силового лонжерона XX',
    net_benefit_rub: -90000,
    meti_sanction_risk: true,
    has_anomaly: true,
    anomaly_text: 'На предыдущих торгах USS зафиксирована оценка R и ремонт передней панели',
  },
  {
    keywords: ['prius', '4419'],
    make: 'Toyota',
    model: 'Prius',
    year: 2020,
    engine_cc: 1797,
    framePrefix: 'ZVW51',
    auction_house: 'TAA',
    lot_number: '4419',
    overall_grade: '4',
    mileage_km: 64000,
    turnkey_cost_rub: 1740000,
    market_price_rf_rub: 1960000,
    verdict: 'green',
    verdict_headline: 'Можно брать • подтверждённый пробег TAA',
    net_benefit_rub: 220000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
  {
    keywords: ['fit', '7820'],
    make: 'Honda',
    model: 'Fit e:HEV',
    year: 2021,
    engine_cc: 1496,
    framePrefix: 'GR3',
    auction_house: 'USS',
    lot_number: '7820',
    overall_grade: '4.5',
    mileage_km: 41000,
    turnkey_cost_rub: 1410000,
    market_price_rf_rub: 1580000,
    verdict: 'green',
    verdict_headline: 'Можно брать • экономия +170 000 ₽ к рынку РФ',
    net_benefit_rub: 170000,
    meti_sanction_risk: false,
    has_anomaly: false,
    anomaly_text: null,
  },
]

export function buildLotSummaryFromTemplate(
  seed: JdmTemplateSeed,
  lotId: string,
  sequenceSuffix: number,
  createdAtIso: string,
): LotSummary {
  const numericSuffix = String(100000 + ((sequenceSuffix * 7919) % 899999))
  const auctionDate = formatJstAuctionDateWithOffset(1, Date.parse(createdAtIso) || Date.now())
  return {
    lot_id: lotId,
    make: seed.make,
    model: seed.model,
    year: seed.year,
    engine_cc: seed.engine_cc,
    frame_id: `${seed.framePrefix}-${numericSuffix}`,
    auction_house: seed.auction_house,
    lot_number: seed.lot_number,
    overall_grade: seed.overall_grade,
    mileage_km: seed.mileage_km,
    turnkey_cost_rub: seed.turnkey_cost_rub,
    market_price_rf_rub: seed.market_price_rf_rub,
    verdict: seed.verdict,
    verdict_headline: seed.verdict_headline,
    net_benefit_rub: seed.net_benefit_rub,
    meti_sanction_risk: seed.meti_sanction_risk,
    has_anomaly: seed.has_anomaly,
    anomaly_text: seed.anomaly_text,
    thumbnail_url: null,
    auction_date: auctionDate,
    is_archived: false,
    archived_at: null,
    archived_reason: null,
    expires_at: computeLotExpiresAt(createdAtIso, auctionDate),
    created_at: createdAtIso,
  }
}

export function pickTemplateForFilename(filename: string, fallbackIndex: number): JdmTemplateSeed {
  const lower = filename.toLowerCase()
  const matched = JDM_TEMPLATES.find((tpl) => tpl.keywords.some((kw) => lower.includes(kw)))
  if (matched) return matched
  const tpl = JDM_TEMPLATES[fallbackIndex % JDM_TEMPLATES.length]
  if (tpl) return tpl
  return JDM_TEMPLATES[0]!
}
