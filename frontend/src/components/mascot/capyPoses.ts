import type { CapyState, KeyFrame, TimingTuple } from './motion'

export type PoseRecord = Record<string, number>

const BASE_POSE: PoseRecord = {
  wSleep: 0,
  wPeek: 0,
  wThink: 0,
  wGreen: 0,
  wYellow: 0,
  wRed: 0,
  wError: 0,
  sit: 0,
  headX: 100,
  headY: 94,
  tilt: 0,
  ear: 0,
  eyeOpen: 0,
  happy: 0,
  lidFlat: 0,
  lidRightExtra: 0,
  sadTilt: 0,
  lookX: 0,
  lookY: 0,
  mouthOpen: 0,
  frown: 0,
  sheet: 0,
  loupe: 0,
  flag: 0,
  caution: 0,
  signal: 0,
  shrug: 0,
  shadowW: 146,
  pawLX: 87,
  pawLY: 143,
  pawRX: 113,
  pawRY: 143,
  pawChin: 0,
}

const createPose = (overrides: Partial<PoseRecord>): PoseRecord => {
  const result: PoseRecord = { ...BASE_POSE }
  for (const [key, value] of Object.entries(overrides)) {
    if (value !== undefined) {
      result[key] = value
    }
  }
  return result
}

export const CAPY_POSES: Record<CapyState, PoseRecord> = {
  sleeping: createPose({
    wSleep: 1,
    headY: 94,
    tilt: 5,
    ear: 16,
    shadowW: 150,
  }),
  peeking: createPose({
    wPeek: 1,
    sit: 0.25,
    headY: 87,
    tilt: 2,
    ear: 2,
    eyeOpen: 0.92,
    lookY: 3.5,
    shadowW: 144,
    pawLX: 85,
    pawRX: 115,
  }),
  thinking: createPose({
    wThink: 1,
    sit: 0.35,
    headX: 96,
    headY: 82,
    tilt: -3,
    ear: -4,
    eyeOpen: 1,
    lookY: 3.5,
    mouthOpen: 0.65,
    sheet: 1,
    loupe: 1,
    pawLX: 68,
    pawLY: 142,
    pawRX: 132,
    pawRY: 126,
  }),
  green: createPose({
    wGreen: 1,
    sit: 0.45,
    headX: 90,
    headY: 80,
    tilt: 3.5,
    ear: 6,
    happy: 1,
    flag: 1,
    pawLX: 74,
    pawLY: 142,
    pawRX: 124,
    pawRY: 122,
  }),
  yellow: createPose({
    wYellow: 1,
    sit: 0.55,
    headX: 88,
    headY: 79,
    tilt: -4,
    ear: 5,
    eyeOpen: 1,
    lidFlat: 0.12,
    lidRightExtra: 0.46,
    lookX: 3,
    lookY: -1,
    frown: 0.35,
    caution: 1,
    shadowW: 144,
    pawLX: 76,
    pawLY: 115,
    pawRX: 142,
    pawRY: 122,
    pawChin: 1,
  }),
  red: createPose({
    wRed: 1,
    sit: 0.45,
    headX: 88,
    headY: 80,
    tilt: -1,
    ear: 9,
    eyeOpen: 1,
    lidFlat: 0.38,
    frown: 1,
    signal: 1,
    shadowW: 148,
    pawLX: 74,
    pawLY: 142,
    pawRX: 144,
    pawRY: 123,
  }),
  error: createPose({
    wError: 1,
    sit: 0.35,
    headX: 98,
    headY: 84,
    tilt: -7,
    ear: 20,
    eyeOpen: 1,
    lidFlat: 0.15,
    sadTilt: 1,
    lookY: -2,
    mouthOpen: 0.25,
    frown: 0.85,
    shrug: 1,
    pawLX: 44,
    pawLY: 122,
    pawRX: 152,
    pawRY: 119,
  }),
}

export const CAPY_DEFAULT_TIMING: Record<string, TimingTuple> = {
  default: [0, 440, 'io'],
  sit: [30, 440, 'io'],
  headY: [50, 480, 'io'],
  tilt: [90, 520, 'io'],
  ear: [140, 360, 'out'],
  eyeOpen: [60, 280, 'out'],
  happy: [80, 260, 'io'],
  paw: [70, 400, 'io'],
  sheet: [120, 380, 'out'],
  loupe: [180, 420, 'out'],
  flag: [120, 420, 'out'],
  caution: [120, 400, 'out'],
  signal: [100, 420, 'out'],
  shrug: [80, 380, 'out'],
}

export function resolveCapyTiming(k: string, _from: number, to: number): TimingTuple {
  if (k.startsWith('paw')) {
    const [d, dur, e] = CAPY_DEFAULT_TIMING.paw ?? [70, 400, 'io']
    return [d + (k.startsWith('pawR') ? 55 : 0), dur, e]
  }
  if (
    (k === 'sheet' || k === 'loupe' || k === 'flag' || k === 'caution' || k === 'signal') &&
    to === 0
  ) {
    return [0, 220, 'in']
  }
  return CAPY_DEFAULT_TIMING[k] ?? CAPY_DEFAULT_TIMING.default ?? [0, 440, 'io']
}

export const CAPY_BLINK: KeyFrame[] = [
  [0, 1],
  [2600, 1],
  [2710, 0],
  [2750, 0],
  [2940, 1, 'out'],
  [3800, 1],
]

export const CAPY_EAR_TWITCH: KeyFrame[] = [
  [0, 0],
  [3800, 0],
  [3920, -14],
  [4040, 0],
  [4160, -9, 'out'],
  [4320, 0],
  [5600, 0],
]

// Horizontal reading saccades: glide left-to-right along a line, hold, quick carriage return
export const CAPY_READ_X: KeyFrame[] = [
  [0, -2.8],
  [850, 2.0],
  [1020, 2.0],
  [1180, -2.8, 'out'],
  [2050, 2.0],
  [2220, 2.0],
  [2380, -2.8, 'out'],
  [3200, 2.4],
  [3420, 2.4],
  [3600, -2.8, 'out'],
]

// Vertical line steps: stays steady on each line while reading horizontally, steps down on return
export const CAPY_READ_Y: KeyFrame[] = [
  [0, -1.2],
  [1020, -1.2],
  [1180, 0.4, 'out'],
  [2220, 0.4],
  [2380, 1.8, 'out'],
  [3420, 1.8],
  [3600, -1.2, 'out'],
]
