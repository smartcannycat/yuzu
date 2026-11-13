import type { VNode } from 'vue'
import {
  MacCrosshair,
  MacGrab,
  MacIbeam,
  MacOpenHand,
  MacPointer,
  MacPointingHand,
  MacResizeEW,
  MacResizeNESW,
  MacResizeNS,
  MacResizeNWSE,
  MacWait,
} from './cursors'
import type { Point } from './measure'
import './cursor.css'

export type CursorKind =
  | 'pointer'
  | 'ibeam'
  | 'crosshair'
  | 'hand'
  | 'open'
  | 'grab'
  | 'wait'
  | 'resize-ns'
  | 'resize-ew'
  | 'resize-nwse'
  | 'resize-nesw'

export type CursorStyle = 'real' | 'large' | 'circle' | 'touch' | 'arrow'

export const GLYPHS: Record<CursorKind, () => VNode> = {
  pointer: MacPointer,
  ibeam: MacIbeam,
  crosshair: MacCrosshair,
  hand: MacPointingHand,
  open: MacOpenHand,
  grab: MacGrab,
  wait: MacWait,
  'resize-ns': MacResizeNS,
  'resize-ew': MacResizeEW,
  'resize-nwse': MacResizeNWSE,
  'resize-nesw': MacResizeNESW,
}

// Where each glyph's hotspot sits inside its box, so the point is the click.
export const HOTSPOT: Record<CursorKind, Point> = {
  pointer: { x: 7.5, y: 5.25 },
  ibeam: { x: 5, y: 8 },
  crosshair: { x: 8.5, y: 8.5 },
  hand: { x: 9.75, y: 3.25 },
  open: { x: 11.7, y: 10.4 },
  grab: { x: 12, y: 12 },
  wait: { x: 8, y: 8 },
  'resize-ns': { x: 10.5, y: 10.5 },
  'resize-ew': { x: 10.5, y: 10.5 },
  'resize-nwse': { x: 10.5, y: 10.5 },
  'resize-nesw': { x: 10.5, y: 10.5 },
}

export const ARROW_HOTSPOT: Point = { x: 4, y: 3 }

/** A ring that spreads from the click point and fades, drawn under the cursor. */
export function ripple(root: HTMLElement, at: Point) {
  const r = document.createElement('span')
  r.className = 'ss-ripple'
  r.style.left = `${at.x}px`
  r.style.top = `${at.y}px`
  root.appendChild(r)
  r.addEventListener('animationend', () => r.remove(), { once: true })
}

export { default as Cursor } from './Cursor.vue'
