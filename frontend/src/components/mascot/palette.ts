import type { CapyState } from './motion'

export const MASCOT_EYES_X = [-20, 20] as const
export const MASCOT_EYE_Y = -14

export const MASCOT_COLORS = {
  skin: '#A56644',
  skinShade: '#8C5235',
  feature: '#5C3520',
  muzzle: '#E5A259',
  muzzleShade: '#CC8B42',
  pupil: '#3C3C3C',
  white: '#FFFFFF',
  cheek: '#FFB2B2',
  shadow: '#E5E5EA',
  scanOrange: '#FF6B00',
  scanGlow: '#FFCE8E',
  sheetBg: '#FFFFFF',
  sheetBorder: '#D1D1D6',
  sheetLine: '#E5E5EA',
  loupeRim: '#4B4B4B',
  loupeGlass: '#DDF4FF',
  loupeEdge: '#84D8FF',
  yuzu: '#FFC800',
  yuzuShade: '#FFB100',
  leaf: '#58CC02',
  leafShade: '#58A700',
  redLight: '#FF4B4B',
  redGlow: '#FF7878',
  redShine: '#FFDFE0',
  housing: '#3C3C3C',
  housingShade: '#262626',
  lampOff: '#555555',
  zzz: ['#9CA3AF', '#6B7280', '#FF6B00'] as const,
} as const

export const DEFAULT_CAPY_LABELS: Record<CapyState, string> = {
  sleeping: 'Ожидание загрузки аукционных листов',
  peeking: 'Листы выбраны • Готова к расчёту',
  thinking: 'Распознаём лист и сверяем базы...',
  green: 'Вердикт Юдзу: Чистый лот',
  yellow: 'Вердикт Юдзу: Есть нюансы',
  red: 'Вердикт Юдзу: Стоп-фактор!',
  error: 'Не удалось распознать бланк',
}
