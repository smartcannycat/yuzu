// motion.ts: pure clock-based motion engine for living SVG illustrations
// Port of the rossark-motion-skill engine with interruptible channel tweens
// and YUZU API contract state resolution.

export type EasingFunction = (t: number) => number

/** Cubic-bezier easing solved by bisection for arbitrary control points. */
export function bezier(x1: number, y1: number, x2: number, y2: number): EasingFunction {
  const cx = 3 * x1
  const bx = 3 * (x2 - x1) - cx
  const ax = 1 - cx - bx
  const cy = 3 * y1
  const by = 3 * (y2 - y1) - cy
  const ay = 1 - cy - by
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t
  const sy = (t: number) => ((ay * t + by) * t + cy) * t
  return (x: number) => {
    if (x <= 0) return 0
    if (x >= 1) return 1
    let lo = 0
    let hi = 1
    let t = x
    for (let i = 0; i < 24; i++) {
      t = (lo + hi) / 2
      if (sx(t) < x) lo = t
      else hi = t
    }
    return sy(t)
  }
}

/** Travel curve: head turns, body sitting up, lids closing. */
export const EASE_IN_OUT: EasingFunction = bezier(0.77, 0, 0.175, 1)
/** Arrival curve: eyes opening, props appearing, flag raising. */
export const EASE_OUT: EasingFunction = bezier(0.23, 1, 0.32, 1)
/** Exit curve: props leaving or dropping away. */
export const EASE_IN: EasingFunction = bezier(0.55, 0, 1, 0.45)
/** Free-fall acceleration curve. */
export const GRAVITY: EasingFunction = (p: number) => p * p
export const LINEAR: EasingFunction = (p: number) => p

export const EASINGS: Record<string, EasingFunction> = {
  io: EASE_IN_OUT,
  out: EASE_OUT,
  in: EASE_IN,
  grav: GRAVITY,
  lin: LINEAR,
}

export type KeyFrame = [ms: number, value: number, curve?: string]

/** Interpolates between keyframes `[ms, value, 'out'?]`, stopping at each key. */
export function track(t: number, keys: KeyFrame[]): number {
  const first = keys[0]
  if (!first) return 0
  if (t <= first[0]) return first[1]
  for (let i = 1; i < keys.length; i++) {
    const k1 = keys[i]
    const k0 = keys[i - 1]
    if (!k1 || !k0) continue
    if (t <= k1[0]) {
      const span = k1[0] - k0[0]
      const p = span > 0 ? (t - k0[0]) / span : 1
      const e = k1[2] === 'out' ? EASE_OUT(p) : EASE_IN_OUT(p)
      return k0[1] + (k1[1] - k0[1]) * e
    }
  }
  const last = keys[keys.length - 1]
  return last ? last[1] : 0
}

/** Smooth sine oscillation in [-1, 1] with phase offset in [0, 1]. */
export function wave(t: number, period: number, phase = 0): number {
  return Math.sin((t / period + phase) * Math.PI * 2)
}

/** Normalized progress through a repeating cycle in [0, 1). */
export function loop(t: number, period: number, phase = 0): number {
  const p = (t / period + phase) % 1
  return p < 0 ? p + 1 : p
}

/** Smooth bell envelope: 0 at both ends, 1 in the middle. */
export function bell(p: number): number {
  return Math.sin(Math.PI * Math.min(1, Math.max(0, p)))
}

/** Deterministic pseudo-random value in [0, 1) for index `i`. */
export function seeded(i: number, salt = 0): number {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
  return x - Math.floor(x)
}

export const clamp01 = (v: number): number => Math.min(1, Math.max(0, v))
export const mix = (a: number, b: number, k: number): number => a + (b - a) * k

export interface ChannelTween {
  from: number
  to: number
  start: number
  dur: number
  ease: EasingFunction
}

export type TimingTuple = [delay: number, duration: number, curve: string]
export type TimingFunction = (k: string, from: number, to: number) => TimingTuple

export interface ChannelsController {
  at(name: string, time: number): number
  retarget(
    targets: Record<string, number>,
    time: number,
    timing: TimingFunction,
    instant?: boolean,
  ): void
  sinceArrived(name: string, time: number): number
  raw: Record<string, ChannelTween>
}

/**
 * Interruptible tweens for named rig channels. Retargeting starts each channel
 * from its current interpolated value so mid-transition changes never snap.
 */
export function createChannels(initial: Record<string, number>): ChannelsController {
  const tw: Record<string, ChannelTween> = {}
  for (const [k, v] of Object.entries(initial)) {
    tw[k] = { from: v, to: v, start: 0, dur: 0, ease: LINEAR }
  }
  function at(name: string, time: number): number {
    const c = tw[name]
    if (!c) return 0
    if (c.dur <= 0 || time >= c.start + c.dur) return time < c.start ? c.from : c.to
    if (time <= c.start) return c.from
    return c.from + (c.to - c.from) * c.ease((time - c.start) / c.dur)
  }
  function retarget(
    targets: Record<string, number>,
    time: number,
    timing: TimingFunction,
    instant = false,
  ): void {
    for (const [k, to] of Object.entries(targets)) {
      const c = tw[k]
      if (!c) continue
      const from = at(k, time)
      const [delay, dur, ease] = timing(k, from, to)
      c.from = from
      c.to = to
      c.start = instant ? time : time + delay
      c.dur = instant ? 0 : dur
      c.ease = EASINGS[ease] ?? EASE_IN_OUT
    }
  }
  function sinceArrived(name: string, time: number): number {
    const c = tw[name]
    if (!c) return -1
    const end = c.start + c.dur
    return time >= end ? time - end : -1
  }
  return { at, retarget, sinceArrived, raw: tw }
}

// --- YUZU Mascot State & API Contract Types ---

/** Canonical visual states of the CapyMascot SVG rig. */
export type CapyState = 'sleeping' | 'peeking' | 'thinking' | 'green' | 'yellow' | 'red' | 'error'

/** Display size mode following the YUZU No-Clown Policy. */
export type MascotSize = 'hero' | 'compact'

/** Backend MascotMood enum from docs/API_DATA_CONTRACTS.md. */
export type MascotMoodContract = 'sleeping' | 'thinking' | 'happy' | 'confused' | 'warning'

/** Backend TrafficLightColor enum from docs/API_DATA_CONTRACTS.md. */
export type TrafficLightColorContract = 'green' | 'yellow' | 'red'

/** Backend BatchStatus enum from docs/API_DATA_CONTRACTS.md. */
export type BatchStatusContract =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'partial_failed'
  | 'failed'

/** Backend ItemProcessingStatus enum from docs/API_DATA_CONTRACTS.md. */
export type ItemProcessingStatusContract = 'queued' | 'processing' | 'ready' | 'failed'

export interface CapyStateResolverInput {
  /** Direct state override when known by the caller. */
  state?: CapyState
  /** Traffic light verdict from LotDetailResponse or RecalculateResponse. */
  verdict?: TrafficLightColorContract | null
  /** MascotMood from BatchProgressResponse.mascot.mood. */
  mood?: MascotMoodContract | null
  /** Batch status from BatchProgressResponse.status. */
  batchStatus?: BatchStatusContract | null
  /** Single item status from BatchItemStatus.status. */
  itemStatus?: ItemProcessingStatusContract | null
  /** Ready and failed counts from BatchProgressResponse. */
  readyCount?: number
  failedCount?: number
  /** Local Dropzone state on Screen 2 (files staged or drag-over active). */
  hasSelectedFiles?: boolean
  isDragOver?: boolean
}

/**
 * Deterministically maps backend API contracts and local UI flags onto one
 * of the 7 canonical CapyMascot rig states.
 */
export function resolveCapyState(input: CapyStateResolverInput): CapyState {
  if (input.state) return input.state

  // 1. Explicit item failure or total batch failure -> error shrug
  if (input.itemStatus === 'failed' || input.batchStatus === 'failed') {
    return 'error'
  }
  if (
    typeof input.readyCount === 'number' &&
    typeof input.failedCount === 'number' &&
    input.readyCount === 0 &&
    input.failedCount > 0 &&
    input.batchStatus !== 'processing' &&
    input.batchStatus !== 'queued'
  ) {
    return 'error'
  }

  // 2. Traffic light verdict on Screen 4 (LotDetailResponse / RecalculateResponse)
  if (input.verdict === 'green') return 'green'
  if (input.verdict === 'yellow') return 'yellow'
  if (input.verdict === 'red') return 'red'

  // 3. Active batch queue processing on Screen 3
  if (input.batchStatus === 'queued' || input.batchStatus === 'processing') {
    return 'thinking'
  }
  if (isPartialFailedBatch(input)) {
    return 'yellow'
  }

  // 4. MascotMood contract fallback from BatchProgressResponse.mascot.mood
  if (input.mood === 'thinking') return 'thinking'
  if (input.mood === 'happy') return 'green'
  if (input.mood === 'warning') return 'red'
  if (input.mood === 'confused') return 'yellow'

  // 5. Local Dropzone staging micro-reaction on Screen 2
  if (input.isDragOver || input.hasSelectedFiles) {
    return 'peeking'
  }

  return 'sleeping'
}

// Helper kept internal to avoid method call on plain object
function isPartialFailedBatch(input: CapyStateResolverInput): boolean {
  return input.batchStatus === 'partial_failed'
}
