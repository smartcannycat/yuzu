// Keystrokes shown as keycaps (act.key): the caps for a combo, and the rows
// the stage draws them in.

/** Where keycaps show. Give `{ wide, compact }` to place them per layout. */
export type KeysAt = 'bottom' | 'top' | 'bottom-left' | 'bottom-right'

// Each keystroke is its own row of caps, so one still fading out never
// changes or recenters when the next arrives
export type Keys = { id: number; caps: string[]; show: boolean; down: boolean }

const KEYCAPS: Record<string, string> = {
  cmd: '⌘',
  shift: '⇧',
  alt: '⌥',
  option: '⌥',
  ctrl: '⌃',
  enter: '↵',
  return: '↵',
  esc: 'esc',
  tab: '⇥',
  up: '↑',
  down: '↓',
  left: '←',
  right: '→',
  backspace: '⌫',
}

/** 'cmd+k' as caps: ['⌘', 'K']. */
export const capsOf = (combo: string) =>
  combo.split('+').map((k) => KEYCAPS[k.trim().toLowerCase()] ?? k.trim().toUpperCase())

export { default as Keycaps } from './Keycaps.vue'
