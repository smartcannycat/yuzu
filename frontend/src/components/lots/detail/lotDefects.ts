import type { BodyPanel, NormalizedDefect } from '@/types/api'

export type DefectTone = 'danger' | 'warning' | 'info'

export interface BodyPanelPinCoord {
  x: number
  y: number
}

export interface BodyPanelShape {
  id: BodyPanel
  kind: 'rect' | 'path'
  d?: string
  x?: number
  y?: number
  width?: number
  height?: number
  rx?: number
}

export function getDefectTone(defect: NormalizedDefect): DefectTone {
  const code = defect.raw_code.toUpperCase()
  if (code.includes('XX') || code.includes('X') || (defect.severity ?? 0) >= 3) {
    return 'danger'
  }
  if (code.includes('W') || code.includes('S') || (defect.severity ?? 0) === 2) {
    return 'warning'
  }
  return 'info'
}

export function getTonePinFill(tone: DefectTone): string {
  if (tone === 'danger') return '#B91C1C'
  if (tone === 'warning') return '#B45309'
  return '#1D4ED8'
}

export function getTonePanelColors(
  tone: DefectTone | null,
  isSelected: boolean,
): { fill: string; stroke: string } {
  if (isSelected) {
    return { fill: '#FFF4ED', stroke: '#FF6B00' }
  }
  if (!tone) {
    return { fill: '#F8F8FA', stroke: '#D1D1D6' }
  }
  if (tone === 'danger') {
    return { fill: '#FEF2F2', stroke: '#EF4444' }
  }
  if (tone === 'warning') {
    return { fill: '#FFFBEB', stroke: '#F59E0B' }
  }
  return { fill: '#EFF6FF', stroke: '#3B82F6' }
}

export const BODY_PANEL_PIN_COORDS: Record<BodyPanel, BodyPanelPinCoord> = {
  front_bumper: { x: 140, y: 38 },
  hood: { x: 140, y: 92 },
  windshield: { x: 140, y: 145 },
  roof: { x: 140, y: 220 },
  tailgate: { x: 140, y: 310 },
  rear_bumper: { x: 140, y: 364 },
  front_left_fender: { x: 55, y: 92 },
  front_right_fender: { x: 225, y: 92 },
  front_left_door: { x: 59, y: 174 },
  front_right_door: { x: 221, y: 174 },
  rear_left_door: { x: 60, y: 251 },
  rear_right_door: { x: 220, y: 251 },
  rear_left_quarter: { x: 59, y: 318 },
  rear_right_quarter: { x: 221, y: 318 },
  left_sill: { x: 26, y: 208 },
  right_sill: { x: 254, y: 208 },
}

export const BODY_PANEL_SHAPES: readonly BodyPanelShape[] = [
  { id: 'left_sill', kind: 'rect', x: 18, y: 128, width: 16, height: 161, rx: 6 },
  { id: 'right_sill', kind: 'rect', x: 246, y: 128, width: 16, height: 161, rx: 6 },
  {
    id: 'front_bumper',
    kind: 'path',
    d: 'M 64 46 C 64 26, 98 18, 140 18 C 182 18, 216 26, 216 46 L 210 58 L 70 58 Z',
  },
  {
    id: 'front_left_fender',
    kind: 'path',
    d: 'M 42 56 L 69 58 L 73 124 L 38 124 L 38 72 C 38 62, 40 57, 42 56 Z',
  },
  {
    id: 'front_right_fender',
    kind: 'path',
    d: 'M 238 56 L 211 58 L 207 124 L 242 124 L 242 72 C 242 62, 240 57, 238 56 Z',
  },
  { id: 'hood', kind: 'path', d: 'M 72 60 L 208 60 L 204 124 L 76 124 Z' },
  { id: 'windshield', kind: 'path', d: 'M 78 127 L 202 127 L 194 163 L 86 163 Z' },
  { id: 'roof', kind: 'rect', x: 86, y: 165, width: 108, height: 109, rx: 10 },
  { id: 'front_left_door', kind: 'path', d: 'M 38 128 L 74 128 L 82 164 L 82 209 L 38 209 Z' },
  {
    id: 'front_right_door',
    kind: 'path',
    d: 'M 206 128 L 242 128 L 242 209 L 198 209 L 198 164 Z',
  },
  { id: 'rear_left_door', kind: 'rect', x: 38, y: 212, width: 44, height: 77, rx: 4 },
  { id: 'rear_right_door', kind: 'rect', x: 198, y: 212, width: 44, height: 77, rx: 4 },
  {
    id: 'rear_left_quarter',
    kind: 'path',
    d: 'M 38 292 L 80 292 L 74 344 L 44 342 C 40 336, 38 324, 38 292 Z',
  },
  {
    id: 'rear_right_quarter',
    kind: 'path',
    d: 'M 200 292 L 242 292 C 242 324, 240 336, 236 342 L 206 344 Z',
  },
  { id: 'tailgate', kind: 'path', d: 'M 86 277 L 194 277 L 202 344 L 78 344 Z' },
  {
    id: 'rear_bumper',
    kind: 'path',
    d: 'M 70 347 L 210 347 L 214 362 C 214 374, 180 382, 140 382 C 100 382, 66 374, 66 362 Z',
  },
]
