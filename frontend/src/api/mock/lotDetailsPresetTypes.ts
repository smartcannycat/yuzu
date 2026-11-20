import type {
  AnomalyAlert,
  BodyPanel,
  DamagedPartItem,
  FuelType,
  NormalizedDefect,
  PastAuctionRecord,
  RiskFlags,
  ServiceWorkItem,
} from '@/types/api'

export interface PresetDetailConfig {
  trim: string | null
  modelCode: string
  auctionBranch: string
  strictness: number
  powerHp: number
  fuelType: FuelType
  driveType: '2WD' | '4WD'
  transmission: string
  colorRu: string
  paintCode: string
  exteriorGrade: string
  interiorGrade: string
  shakenUntil: string | null
  recyclingYen: number
  equipment: string[]
  defects: NormalizedDefect[]
  parts: DamagedPartItem[]
  serviceWorks: ServiceWorkItem[]
  bodySummaryRu: string
  interiorSummaryRu: string
  reasoningBullets: string[]
  inspectorNotesRu: string[]
  inspectorNotesRaw: string[]
  sellerCommentsRu: string[]
  ocrWarnings: string[]
  analogsCount: number
  anomalies: AnomalyAlert[]
  history: PastAuctionRecord[]
  hasCriticalAnomaly: boolean
  isCommercialUtilDefault?: boolean
  riskFlagsOverride?: Partial<RiskFlags>
}

export const PANEL_LABELS_RU: Record<BodyPanel, string> = {
  front_bumper: 'Передний бампер',
  rear_bumper: 'Задний бампер',
  hood: 'Капот',
  roof: 'Крыша',
  tailgate: 'Пятая дверь / крышка багажника',
  front_left_fender: 'Переднее левое крыло',
  front_right_fender: 'Переднее правое крыло',
  front_left_door: 'Передняя левая дверь',
  front_right_door: 'Передняя правая дверь',
  rear_left_door: 'Задняя левая дверь',
  rear_right_door: 'Задняя правая дверь',
  rear_left_quarter: 'Заднее левое крыло',
  rear_right_quarter: 'Заднее правое крыло',
  left_sill: 'Левый порог',
  right_sill: 'Правый порог',
  windshield: 'Лобовое стекло',
  other: 'Прочие элементы',
}
