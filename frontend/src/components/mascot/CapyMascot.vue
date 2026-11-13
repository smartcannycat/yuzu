<script setup lang="ts">
// CapyMascot.vue: YUZU "Zen Inspector" Capybara SVG rig
//
// Built on the sleeping capybara base rig (viewBox 200 x 170, floor y = 150,
// head 88 wide centered at (0, 0) with neck pivot (0, 30)).
// Follows duolingo-character-style and rossark-motion-skill.

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  bell,
  clamp01,
  createChannels,
  loop,
  mix,
  resolveCapyState,
  seeded,
  track,
  wave,
  type BatchStatusContract,
  type CapyState,
  type ItemProcessingStatusContract,
  type KeyFrame,
  type MascotMoodContract,
  type MascotSize,
  type TimingTuple,
  type TrafficLightColorContract,
} from './motion'

export interface CapyMascotProps {
  /** Direct canonical state override. */
  state?: CapyState
  /** Traffic light verdict from LotDetailResponse / RecalculateResponse. */
  verdict?: TrafficLightColorContract | null
  /** MascotMood from BatchProgressResponse.mascot.mood. */
  mood?: MascotMoodContract | null
  /** Batch status from BatchProgressResponse.status. */
  batchStatus?: BatchStatusContract | null
  /** Single item status from BatchItemStatus.status. */
  itemStatus?: ItemProcessingStatusContract | null
  /** Counts from BatchProgressResponse. */
  readyCount?: number
  failedCount?: number
  /** Local Dropzone state on Screen 2 (files staged or drag-over active). */
  hasSelectedFiles?: boolean
  isDragOver?: boolean
  /** Display mode: 'hero' (208x176 + optional chip) or 'compact' (80x80 avatar). */
  size?: MascotSize
  /** Custom status label for the pill badge below hero mascot. */
  badgeText?: string
  /** Hide the pill badge below the mascot. Defaults to true when size === 'compact'. */
  hideBadge?: boolean
}

const props = withDefaults(defineProps<CapyMascotProps>(), {
  state: undefined,
  verdict: null,
  mood: null,
  batchStatus: null,
  itemStatus: null,
  readyCount: undefined,
  failedCount: undefined,
  hasSelectedFiles: false,
  isDragOver: false,
  size: 'hero',
  badgeText: undefined,
  hideBadge: undefined,
})

const activeState = computed<CapyState>(() =>
  resolveCapyState({
    state: props.state,
    verdict: props.verdict,
    mood: props.mood,
    batchStatus: props.batchStatus,
    itemStatus: props.itemStatus,
    readyCount: props.readyCount,
    failedCount: props.failedCount,
    hasSelectedFiles: props.hasSelectedFiles,
    isDragOver: props.isDragOver,
  }),
)

const isCompact = computed(() => props.size === 'compact')
const shouldHideBadge = computed(() => props.hideBadge ?? isCompact.value)

const DEFAULT_LABELS: Record<CapyState, string> = {
  sleeping: 'Ожидание загрузки аукционных листов',
  peeking: 'Листы выбраны • Готова к расчёту',
  thinking: 'Распознаём лист и сверяем базы...',
  green: 'Вердикт Юдзу: Чистый лот',
  yellow: 'Вердикт Юдзу: Есть нюансы',
  red: 'Вердикт Юдзу: Стоп-фактор!',
  error: 'Не удалось распознать бланк',
}

const statusLabel = computed(() => props.badgeText || DEFAULT_LABELS[activeState.value])

// --- Palette (Duolingo flat shape colors + YUZU Clean Light tokens) ---
const C = {
  skin: '#A56644', // Grizzly
  skinShade: '#8C5235', // One step darker skin
  feature: '#5C3520', // Nostrils, mouth, closed eyes, poles
  muzzle: '#E5A259', // Monkey
  muzzleShade: '#CC8B42', // Paw over muzzle shade
  pupil: '#3C3C3C',
  white: '#FFFFFF',
  cheek: '#FFB2B2', // Flamingo
  shadow: '#E5E5EA', // Clean Light border/shadow pill
  scanOrange: '#FF6B00', // Farpost Orange accent
  scanGlow: '#FFCE8E', // Cheetah
  sheetBg: '#FFFFFF',
  sheetBorder: '#D1D1D6',
  sheetLine: '#E5E5EA',
  loupeRim: '#4B4B4B', // Eel
  loupeGlass: '#DDF4FF', // Iguana
  loupeEdge: '#84D8FF', // Blue Jay
  yuzu: '#FFC800', // Bee
  yuzuShade: '#FFB100', // Lion
  leaf: '#58CC02', // Feather Green
  leafShade: '#58A700', // Tree Frog
  redLight: '#FF4B4B', // Cardinal
  redGlow: '#FF7878', // Crab
  redShine: '#FFDFE0', // Walking Fish
  housing: '#3C3C3C',
  housingShade: '#262626',
  lampOff: '#555555',
  zzz: ['#9CA3AF', '#6B7280', '#FF6B00'],
}

// --- Key poses per state (every channel can tween from any current value) ---
type PoseRecord = Record<string, number>

const POSES: Record<CapyState, PoseRecord> = {
  sleeping: {
    wSleep: 1,
    wPeek: 0,
    wThink: 0,
    wGreen: 0,
    wYellow: 0,
    wRed: 0,
    wError: 0,
    sit: 0,
    headX: 100,
    headY: 94,
    tilt: 5,
    ear: 16,
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
    shadowW: 150,
    pawLX: 87,
    pawLY: 143,
    pawRX: 113,
    pawRY: 143,
    pawChin: 0,
  },
  peeking: {
    wSleep: 0,
    wPeek: 1,
    wThink: 0,
    wGreen: 0,
    wYellow: 0,
    wRed: 0,
    wError: 0,
    sit: 0.25,
    headX: 100,
    headY: 87,
    tilt: 2,
    ear: 2,
    eyeOpen: 0.92,
    happy: 0,
    lidFlat: 0,
    lidRightExtra: 0,
    sadTilt: 0,
    lookX: 0,
    lookY: 3.5,
    mouthOpen: 0,
    frown: 0,
    sheet: 0,
    loupe: 0,
    flag: 0,
    caution: 0,
    signal: 0,
    shrug: 0,
    shadowW: 144,
    pawLX: 85,
    pawLY: 143,
    pawRX: 115,
    pawRY: 143,
    pawChin: 0,
  },
  thinking: {
    wSleep: 0,
    wPeek: 0,
    wThink: 1,
    wGreen: 0,
    wYellow: 0,
    wRed: 0,
    wError: 0,
    sit: 0.35,
    headX: 96,
    headY: 82,
    tilt: -3,
    ear: -4,
    eyeOpen: 1,
    happy: 0,
    lidFlat: 0,
    lidRightExtra: 0,
    sadTilt: 0,
    lookX: 0,
    lookY: 3.5,
    mouthOpen: 0.65,
    frown: 0,
    sheet: 1,
    loupe: 1,
    flag: 0,
    caution: 0,
    signal: 0,
    shrug: 0,
    shadowW: 146,
    pawLX: 68,
    pawLY: 142,
    pawRX: 132,
    pawRY: 126,
    pawChin: 0,
  },
  green: {
    wSleep: 0,
    wPeek: 0,
    wThink: 0,
    wGreen: 1,
    wYellow: 0,
    wRed: 0,
    wError: 0,
    sit: 0.45,
    headX: 90,
    headY: 80,
    tilt: 3.5,
    ear: 6,
    eyeOpen: 0,
    happy: 1,
    lidFlat: 0,
    lidRightExtra: 0,
    sadTilt: 0,
    lookX: 0,
    lookY: 0,
    mouthOpen: 0,
    frown: 0,
    sheet: 0,
    loupe: 0,
    flag: 1,
    caution: 0,
    signal: 0,
    shrug: 0,
    shadowW: 146,
    pawLX: 74,
    pawLY: 142,
    pawRX: 124,
    pawRY: 122,
    pawChin: 0,
  },
  yellow: {
    wSleep: 0,
    wPeek: 0,
    wThink: 0,
    wGreen: 0,
    wYellow: 1,
    wRed: 0,
    wError: 0,
    sit: 0.55,
    headX: 88,
    headY: 79,
    tilt: -4,
    ear: 5,
    eyeOpen: 1,
    happy: 0,
    lidFlat: 0.12,
    lidRightExtra: 0.46,
    sadTilt: 0,
    lookX: 3,
    lookY: -1,
    mouthOpen: 0,
    frown: 0.35,
    sheet: 0,
    loupe: 0,
    flag: 0,
    caution: 1,
    signal: 0,
    shrug: 0,
    shadowW: 144,
    pawLX: 76,
    pawLY: 115,
    pawRX: 142,
    pawRY: 122,
    pawChin: 1,
  },
  red: {
    wSleep: 0,
    wPeek: 0,
    wThink: 0,
    wGreen: 0,
    wYellow: 0,
    wRed: 1,
    wError: 0,
    sit: 0.45,
    headX: 88,
    headY: 80,
    tilt: -1,
    ear: 9,
    eyeOpen: 1,
    happy: 0,
    lidFlat: 0.38,
    lidRightExtra: 0,
    sadTilt: 0,
    lookX: 0,
    lookY: 0,
    mouthOpen: 0,
    frown: 1,
    sheet: 0,
    loupe: 0,
    flag: 0,
    caution: 0,
    signal: 1,
    shrug: 0,
    shadowW: 148,
    pawLX: 74,
    pawLY: 142,
    pawRX: 144,
    pawRY: 123,
    pawChin: 0,
  },
  error: {
    wSleep: 0,
    wPeek: 0,
    wThink: 0,
    wGreen: 0,
    wYellow: 0,
    wRed: 0,
    wError: 1,
    sit: 0.35,
    headX: 98,
    headY: 84,
    tilt: -7,
    ear: 20,
    eyeOpen: 1,
    happy: 0,
    lidFlat: 0.15,
    lidRightExtra: 0,
    sadTilt: 1,
    lookX: 0,
    lookY: -2,
    mouthOpen: 0.25,
    frown: 0.85,
    sheet: 0,
    loupe: 0,
    flag: 0,
    caution: 0,
    signal: 0,
    shrug: 1,
    shadowW: 146,
    pawLX: 44,
    pawLY: 122,
    pawRX: 152,
    pawRY: 119,
    pawChin: 0,
  },
}

const DEFAULT_TIMING: Record<string, TimingTuple> = {
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

const BLINK: KeyFrame[] = [
  [0, 1],
  [2600, 1],
  [2710, 0],
  [2750, 0],
  [2940, 1, 'out'],
  [3800, 1],
]

const EAR_TWITCH: KeyFrame[] = [
  [0, 0],
  [3800, 0],
  [3920, -14],
  [4040, 0],
  [4160, -9, 'out'],
  [4320, 0],
  [5600, 0],
]

// Horizontal reading saccades: glide left-to-right along a line, hold, quick carriage return
const READ_X: KeyFrame[] = [
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
const READ_Y: KeyFrame[] = [
  [0, -1.2],
  [1020, -1.2],
  [1180, 0.4, 'out'],
  [2220, 0.4],
  [2380, 1.8, 'out'],
  [3420, 1.8],
  [3600, -1.2, 'out'],
]

const uid = `yuzu-capy-${Math.random().toString(36).slice(2, 8)}`
const ch = createChannels(POSES[activeState.value])

// --- Clock: single rAF loop, paused off screen / hidden / reduced motion ---
const root = ref<HTMLElement | null>(null)
const now = ref(performance.now())
const reduced = ref(false)
let t0 = performance.now()
let raf = 0
let onScreen = true
let mql: MediaQueryList | null = null
let io: IntersectionObserver | null = null

function frame(ts: number) {
  now.value = ts
  raf = requestAnimationFrame(frame)
}
function start() {
  if (raf || reduced.value || !onScreen || document.hidden) return
  raf = requestAnimationFrame(frame)
}
function stop() {
  if (raf) cancelAnimationFrame(raf)
  raf = 0
}
function onVisibility() {
  if (document.hidden) stop()
  else start()
}
function onReducedChange() {
  reduced.value = !!mql?.matches
  if (reduced.value) {
    stop()
    now.value = performance.now()
  } else {
    start()
  }
}

watch(activeState, (nextState) => {
  const T = performance.now()
  ch.retarget(
    POSES[nextState],
    T,
    (k, _from, to) => {
      if (k.startsWith('paw')) {
        const [d, dur, e] = DEFAULT_TIMING.paw ?? [70, 400, 'io']
        return [d + (k.startsWith('pawR') ? 55 : 0), dur, e]
      }
      if (
        (k === 'sheet' || k === 'loupe' || k === 'flag' || k === 'caution' || k === 'signal') &&
        to === 0
      ) {
        return [0, 220, 'in']
      }
      return DEFAULT_TIMING[k] ?? DEFAULT_TIMING.default ?? [0, 440, 'io']
    },
    reduced.value,
  )
  if (reduced.value) now.value = T
  else start()
})

onMounted(() => {
  t0 = performance.now()
  mql = window.matchMedia?.('(prefers-reduced-motion: reduce)') ?? null
  reduced.value = !!mql?.matches
  mql?.addEventListener?.('change', onReducedChange)
  document.addEventListener('visibilitychange', onVisibility)
  if ('IntersectionObserver' in window && root.value) {
    io = new IntersectionObserver(([entry]) => {
      onScreen = !!entry?.isIntersecting
      if (onScreen) start()
      else stop()
    })
    io.observe(root.value)
  }
  start()
})

onBeforeUnmount(() => {
  stop()
  io?.disconnect()
  mql?.removeEventListener?.('change', onReducedChange)
  document.removeEventListener('visibilitychange', onVisibility)
})

// --- Frame pose evaluation ---
const EYES = [-20, 20] as const
const EYE_Y = -14

const p = computed(() => {
  const T = now.value
  const t = reduced.value ? 0 : T - t0
  const c = (k: string, dt = 0) => ch.at(k, T - dt)

  const wS = c('wSleep')
  const wP = c('wPeek')
  const wT = c('wThink')
  const wG = c('wGreen')
  const wY = c('wYellow')
  const wR = c('wRed')
  const wE = c('wError')

  // In compact mode (Screen 4 Verdict Cards), dampen continuous idle amplitude after arrival
  const idleScale = isCompact.value ? 0.55 : 1

  // Breathing: smooth cross-fade of mood rhythms
  const breath = (tt: number) =>
    (wS * wave(tt, 4200) +
      wP * 0.7 * wave(tt, 2800) +
      wT * 0.65 * wave(tt, 1900) +
      (wG + wY + wR + wE) * 0.55 * wave(tt, 3400)) *
    idleScale
  const b = breath(t)
  const bLate = breath(t - 150)

  // Body: stays a cozy round loaf in all moods, volume kept while breathing
  const sit = c('sit')
  const W0 = mix(126, 114, sit)
  const H0 = mix(56, 61, sit)
  const sy = 1 + 0.026 * b
  const sx = 1 / Math.pow(sy, 0.6)
  const bodyW = W0 * sx
  const bodyH = H0 * sy
  const bodyBottom = 150

  // Head: follows breath a beat later + subtle state head motion
  const redArrived = ch.raw.signal?.to === 1 ? ch.sinceArrived('signal', T) : -1
  const redShake =
    redArrived >= 0 && redArrived < 850 && !reduced.value
      ? 4.2 * bell(redArrived / 850) * wave(redArrived, 280)
      : 0

  const tiltIdle = (tt: number) =>
    (wS * 1.4 * wave(tt, 4200, 0.15) +
      wT * 2.2 * wave(tt, 3200, 0.25) +
      wG * 2.0 * wave(tt, 2800, 0.1) +
      wY * 1.4 * wave(tt, 3600, 0.2) +
      wE * 1.6 * wave(tt, 3800, 0.3)) *
    idleScale

  const tilt = c('tilt') + tiltIdle(t)
  const tiltLate = c('tilt', 110) + tiltIdle(t - 110)
  const ft = tiltLate - tilt // follow-through lag for ears and held props

  const hx = c('headX') + redShake + wT * 1.2 * wave(t, 3200, 0.1) * idleScale
  const hy = c('headY') - H0 * 0.026 * bLate * 0.85

  // Ears: asymmetric wave + sleepy right-ear twitch
  const ear = c('ear')
  const earWaveAmp = (wT * 0.9 + wS * 0.35 + (wG + wY + wR + wE) * 0.5) * idleScale
  const twitch = wS * track(loop(t, 5600) * 5600, EAR_TWITCH)
  const earL = -(ear + 2.8 * earWaveAmp * wave(t, 3100)) + 0.6 * ft
  const earR = ear + 2.8 * earWaveAmp * wave(t, 2700, 0.37) + twitch + 0.6 * ft

  // Inspection 2-phase cycle during THINKING (6400 ms period):
  // Phase 1 (0..0.55): reading lines left-to-right while beam sweeps
  // Phase 2 (0.55..1.0): bringing loupe closer and squinting right eye
  const thinkCycle = loop(t, 6400)
  const thinkZoom = wT * bell(clamp01((thinkCycle - 0.52) / 0.44))

  // Eyes: blink while open; pupils track scan beam or prop
  const blink = track(loop(t, 3800) * 3800, BLINK)
  const awakeWeight = clamp01(1 - wS - wG)
  const open = clamp01(c('eyeOpen') * mix(1, blink, awakeWeight))

  const readT = loop(t, 3600) * 3600
  const scanLookX = wT * track(readT, READ_X)
  const scanLookY = wT * track(readT, READ_Y)
  const lookX = c('lookX') + scanLookX + redShake * 0.45
  const lookY = c('lookY') + scanLookY

  const happy = c('happy')
  const lidFlat = c('lidFlat')
  const lidRightExtra = c('lidRightExtra') + 0.38 * thinkZoom
  const sadTilt = c('sadTilt')

  const baseLidClose = 32 * 0.9 * (1 - open)
  const lowH = 32 * 0.26 * (1 - open) + 1.2 + 5 * thinkZoom * 0.5
  const closedOp = clamp01((0.28 - open) / 0.28)
  const closedY = EYE_Y + 9 - 4 * happy
  const closedCurve = mix(4, -9, happy)

  const eyes = EYES.map((cx, idx) => {
    const extraTop = idx === 1 ? 30 * lidRightExtra : 0
    const flatTop = 30 * lidFlat
    const lidH = Math.min(34, Math.max(baseLidClose, flatTop, extraTop) + 2)
    // Outward downward slant for sad/apologetic error state (no eyebrows needed)
    const lidAngle = sadTilt * (idx === 0 ? -14 : 14)
    return {
      cx,
      pupilX: cx - 5 + lookX,
      pupilY: EYE_Y - 10 + lookY,
      lidH,
      lowY: EYE_Y + 15 - lowH,
      lidTf: `rotate(${lidAngle} ${cx} ${EYE_Y - 4})`,
      closed: `M ${cx - 8} ${closedY} Q ${cx} ${closedY + closedCurve} ${cx + 8} ${closedY}`,
    }
  })

  // Mouth: morphs between smile (frown=0), focused "o" (mouthOpen>0), and stern/sad arch (frown=1)
  const mo = c('mouthOpen')
  const fr = c('frown')
  const mw = 6.2 - 1.6 * mo
  const my = 23 + 1.5 * fr
  const arch = mix(4.2, -4.8, fr)
  const mouth =
    `M ${-mw} ${my} ` +
    `Q 0 ${my + arch + 4.5 * mo} ${mw} ${my} ` +
    `Q 0 ${my + arch - 3.2 * mo} ${-mw} ${my} Z`

  // Paws
  const pawLX = c('pawLX') - wE * 2 * wave(t, 2800) * idleScale
  const pawLY = c('pawLY') + wT * 1.2 * wave(t, 1900)
  const pawRX = c('pawRX') + wE * 2 * wave(t, 2800, 0.5) * idleScale
  const pawRY =
    c('pawRY') + wT * (-4 * thinkZoom + 2.5 * wave(t, 3200)) + wG * 1.5 * wave(t, 2800) * idleScale
  const pawChin = c('pawChin')
  const shrug = c('shrug')

  // Prop 1: Auction Sheet + Scan Beam + Loupe (THINKING)
  const sheetVal = c('sheet')
  const sheetY = (1 - sheetVal) * 28 + 1.8 * wave(t, 2600)
  const scanProgress = (wave(t, 2200) + 1) / 2 // 0..1 vertical sweep
  const scanY = 105 + scanProgress * 28

  const loupeVal = c('loupe')
  const loupeScale = 0.88 + 0.12 * loupeVal + 0.08 * thinkZoom
  const loupeRot = -12 + 8 * wave(t, 3200) + 6 * thinkZoom + 1.1 * ft
  const loupeTf =
    `translate(${pawRX} ${pawRY}) ` +
    `rotate(${loupeRot}) scale(${loupeScale}) translate(${-pawRX} ${-pawRY})`

  // Prop 2: Green Verdict Flag with Yuzu Finial (GREEN)
  const flagVal = c('flag')
  const flagArrived = ch.raw.flag?.to === 1 ? ch.sinceArrived('flag', T) : -1
  const flagEntranceWave =
    flagArrived >= 0 && flagArrived < 1200 && !reduced.value
      ? 9.5 * bell(flagArrived / 1200) * wave(flagArrived, 380)
      : 0
  const flagRot =
    14 +
    (1 - flagVal) * 22 +
    flagEntranceWave +
    2.4 * wG * wave(t, 2800, 0.15) * idleScale +
    1.3 * ft
  const flagTf = `translate(${pawRX} ${pawRY + 4}) rotate(${flagRot}) translate(0 ${(1 - flagVal) * 18})`
  const yuzuRock = 1.6 * ft + 0.5 * flagEntranceWave

  // Prop 3: Yellow Caution Sign (YELLOW)
  const cautionVal = c('caution')
  const cautionArrived = ch.raw.caution?.to === 1 ? ch.sinceArrived('caution', T) : -1
  const cautionEntrance =
    cautionArrived >= 0 && cautionArrived < 1000 && !reduced.value
      ? 6 * bell(cautionArrived / 1000) * wave(cautionArrived, 340)
      : 0
  const cautionRot =
    8 + (1 - cautionVal) * 18 + cautionEntrance + 1.8 * wY * wave(t, 3400) * idleScale + 1.1 * ft
  const cautionTf = `translate(${pawRX + 2} ${pawRY + 4}) rotate(${cautionRot}) translate(0 ${(1 - cautionVal) * 18})`
  const cautionPulse = bell(loop(t, 1600)) * cautionVal * wY

  // Prop 4: Red Stop-Factor Traffic Light (RED)
  const sigVal = c('signal')
  const sigRot = 1.2 * wR * wave(t, 3200) * idleScale + 0.8 * ft
  const sigTf = `translate(${pawRX + 4} ${pawRY + 4}) rotate(${sigRot}) translate(0 ${(1 - sigVal) * 22})`
  const redRings = [0, 1].map((i) => {
    const q = loop(t, 1250, i * 0.5)
    const offset = 4 * q
    return {
      op: bell(q) * sigVal * wR,
      offset,
    }
  })

  // Prop 5: Floating Question Marks on OCR Error (ERROR)
  const questions = [0, 1].map((i) => {
    const q = loop(t, 3200, i * 0.5)
    const qx = 148 + i * 14 + 3 * wave(t, 1800, i * 0.4)
    const qy = 66 - 26 * q
    const qs = 0.85 + 0.25 * q
    return {
      op: bell(q) * shrug * wE,
      tf: `translate(${qx} ${qy}) scale(${qs}) rotate(${8 * wave(t, 2000, i)})`,
      color: i === 0 ? C.scanOrange : C.zzz[1],
    }
  })

  // Zzz glyphs (SLEEPING)
  const zzz = [0, 1, 2].map((i) => {
    const q = loop(t, 3600, i / 3)
    const zs = 3.5 + 3.5 * q
    const zx = 142 + 16 * q + 2 * wave(t, 1700, i * 0.3)
    const zy = 68 - 36 * q
    return {
      op: bell(q) * wS,
      color: C.zzz[i] ?? C.zzz[0],
      d: `M ${zx - zs} ${zy - zs} L ${zx + zs} ${zy - zs} L ${zx - zs} ${zy + zs} L ${zx + zs} ${zy + zs}`,
    }
  })

  const shadowW = c('shadowW') * (1 + 0.015 * b)

  return {
    body: {
      x: hx - bodyW / 2,
      y: bodyBottom - bodyH,
      w: bodyW,
      h: bodyH,
      rx: Math.min(bodyW, bodyH) * 0.46,
    },
    headTf: `translate(${hx} ${hy}) rotate(${tilt} 0 30)`,
    earL,
    earR,
    open,
    eyes,
    lowH,
    closedOp,
    cheekY: 6 - 2 * happy,
    mouth,
    shadowW,
    pawL: {
      x: pawLX,
      y: pawLY,
      w: 22 + 3 * shrug,
      h: 14 - 1 * shrug,
      rot: -18 * shrug,
      fill: pawChin > 0.4 ? C.muzzleShade : C.muzzle,
    },
    pawR: {
      x: pawRX,
      y: pawRY,
      w: 22 + 3 * shrug,
      h: 14 - 1 * shrug,
      rot: 18 * shrug,
      fill: C.muzzle,
    },
    sheetOp: clamp01(sheetVal * 2.2),
    sheetY,
    scanY,
    loupeOp: clamp01(loupeVal * 2.2),
    loupeTf,
    flagOp: clamp01(flagVal * 2.5),
    flagTf,
    yuzuRock,
    cautionOp: clamp01(cautionVal * 2.5),
    cautionTf,
    cautionPulse,
    sigOp: clamp01(sigVal * 2.5),
    sigTf,
    redRings,
    questions,
    zzz,
  }
})
</script>

<template>
  <div
    ref="root"
    class="mascot-container flex flex-col items-center justify-center select-none"
    :class="isCompact ? 'h-full w-full' : 'w-full'"
  >
    <!-- SVG Mascot Stage -->
    <div
      :class="
        isCompact
          ? 'relative flex h-full w-full items-center justify-center'
          : 'relative flex h-44 w-52 items-center justify-center'
      "
    >
      <svg
        :viewBox="isCompact ? '8 4 186 156' : '0 0 200 170'"
        class="h-full w-full overflow-visible"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        :aria-label="statusLabel"
      >
        <defs>
          <clipPath v-for="(cx, i) in EYES" :id="`${uid}-eye${i}`" :key="`e${i}`">
            <rect :x="cx - 10" :y="EYE_Y - 13" width="20" height="26" rx="10" />
          </clipPath>
          <clipPath v-for="(cx, i) in EYES" :id="`${uid}-lid${i}`" :key="`l${i}`">
            <rect :x="cx - 12" :y="EYE_Y - 15" width="24" height="30" rx="12" />
          </clipPath>
          <clipPath :id="`${uid}-sheet-clip`">
            <rect x="44" y="102" width="48" height="38" rx="6" />
          </clipPath>
        </defs>

        <!-- Floor shadow: flat pill (Duolingo flat perspective rule) -->
        <rect
          :x="100 - p.shadowW / 2"
          y="144"
          :width="p.shadowW"
          height="12"
          rx="6"
          :fill="C.shadow"
        />

        <!-- Body: sleeping loaf <-> sitting capsule -->
        <rect
          :x="p.body.x"
          :y="p.body.y"
          :width="p.body.w"
          :height="p.body.h"
          :rx="p.body.rx"
          :fill="C.skin"
        />

        <!-- Head group (neck pivot at (0, 30)) -->
        <g :transform="p.headTf">
          <!-- Ears: rounded capsules one shade darker -->
          <rect
            x="-38"
            y="-45"
            width="15"
            height="18"
            rx="7.5"
            :fill="C.skinShade"
            :transform="`rotate(${p.earL} -30 -30)`"
          />
          <rect
            x="23"
            y="-45"
            width="15"
            height="18"
            rx="7.5"
            :fill="C.skinShade"
            :transform="`rotate(${p.earR} 30 -30)`"
          />

          <!-- Head: rounded tombstone block -->
          <rect x="-44" y="-38" width="88" height="76" rx="34" :fill="C.skin" />

          <!-- Muzzle -->
          <rect x="-32" y="0" width="64" height="36" rx="17" :fill="C.muzzle" />

          <!-- Cheeks -->
          <rect x="-42" :y="p.cheekY" width="11" height="7" rx="3.5" :fill="C.cheek" />
          <rect x="31" :y="p.cheekY" width="11" height="7" rx="3.5" :fill="C.cheek" />

          <!-- Nostrils + morphing mouth -->
          <rect x="-9" y="8" width="6" height="8" rx="3" :fill="C.feature" />
          <rect x="3" y="8" width="6" height="8" rx="3" :fill="C.feature" />
          <path
            :d="p.mouth"
            :fill="C.feature"
            :stroke="C.feature"
            stroke-width="3"
            stroke-linejoin="round"
            stroke-linecap="round"
          />

          <!-- Live eyes: white pills, clipped pupils, clipped skin lids +2 larger -->
          <g v-for="(e, i) in p.eyes" :key="`eye${i}`">
            <g v-show="p.open > 0.04">
              <rect :x="e.cx - 10" :y="EYE_Y - 13" width="20" height="26" rx="10" :fill="C.white" />
              <g :clip-path="`url(#${uid}-eye${i})`">
                <rect :x="e.pupilX" :y="e.pupilY" width="10" height="15" rx="5" :fill="C.pupil" />
                <circle :cx="e.pupilX + 3.5" :cy="e.pupilY + 4" r="2.2" :fill="C.white" />
              </g>
              <g :clip-path="`url(#${uid}-lid${i})`">
                <rect
                  :x="e.cx - 14"
                  :y="EYE_Y - 17"
                  width="28"
                  :height="e.lidH"
                  :fill="C.skin"
                  :transform="e.lidTf"
                />
                <rect :x="e.cx - 12" :y="e.lowY" width="24" :height="p.lowH" :fill="C.skin" />
              </g>
            </g>
            <path
              v-show="p.closedOp > 0.01"
              :d="e.closed"
              :opacity="p.closedOp"
              fill="none"
              :stroke="C.feature"
              stroke-width="3.5"
              stroke-linecap="round"
            />
          </g>
        </g>

        <!-- Prop 1A: Auction Sheet with Farpost Orange Scan Beam (THINKING) -->
        <g
          v-if="p.sheetOp > 0.01"
          :opacity="p.sheetOp"
          :transform="`translate(0 ${p.sheetY}) rotate(-4 68 122)`"
        >
          <rect x="42" y="100" width="52" height="42" rx="7" :fill="C.sheetBorder" />
          <rect x="44" y="101" width="48" height="39" rx="6" :fill="C.sheetBg" />
          <!-- Sheet Header & Mini Diagram -->
          <rect x="48" y="105" width="22" height="4" rx="2" :fill="C.scanOrange" />
          <rect x="74" y="105" width="14" height="4" rx="2" :fill="C.sheetLine" />
          <rect x="48" y="113" width="24" height="15" rx="4" :fill="C.loupeGlass" />
          <rect x="52" y="116" width="16" height="9" rx="3" :fill="C.loupeEdge" />
          <rect x="75" y="113" width="13" height="3.5" rx="1.75" :fill="C.sheetLine" />
          <rect x="75" y="119" width="11" height="3.5" rx="1.75" :fill="C.sheetLine" />
          <rect x="48" y="131" width="40" height="4" rx="2" :fill="C.sheetLine" />
          <!-- Sweeping Scan Beam clipped to sheet -->
          <g :clip-path="`url(#${uid}-sheet-clip)`">
            <rect x="42" :y="p.scanY - 4" width="52" height="8" :fill="C.scanGlow" opacity="0.55" />
            <rect x="42" :y="p.scanY" width="52" height="3" rx="1.5" :fill="C.scanOrange" />
          </g>
        </g>

        <!-- Prop 1B: Inspector Loupe (drawn before right paw so paw grips handle) -->
        <g v-if="p.loupeOp > 0.01" :opacity="p.loupeOp" :transform="p.loupeTf">
          <rect
            :x="p.pawR.x - 3"
            :y="p.pawR.y - 26"
            width="6"
            height="34"
            rx="3"
            :fill="C.feature"
          />
          <circle :cx="p.pawR.x" :cy="p.pawR.y - 34" r="16" :fill="C.loupeRim" />
          <circle :cx="p.pawR.x" :cy="p.pawR.y - 34" r="11.5" :fill="C.loupeGlass" />
          <rect
            :x="p.pawR.x - 6"
            :y="p.pawR.y - 41"
            width="4"
            height="9"
            rx="2"
            :fill="C.white"
            :transform="`rotate(-25 ${p.pawR.x - 4} ${p.pawR.y - 37})`"
          />
        </g>

        <!-- Prop 2: Green Verdict Flag with Yuzu Citrus Finial (GREEN) -->
        <g v-if="p.flagOp > 0.01" :opacity="p.flagOp" :transform="p.flagTf">
          <!-- Flag cloth -->
          <g transform="translate(2 -80)">
            <rect x="0" y="0" width="50" height="35" rx="9" :fill="C.leaf" />
            <!-- White Checkmark -->
            <path
              d="M 15 17.5 L 22.5 24.5 L 36.5 11"
              fill="none"
              :stroke="C.white"
              stroke-width="5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </g>
          <!-- Flagpole -->
          <rect x="-3.5" y="-84" width="7" height="94" rx="3.5" :fill="C.feature" />
          <!-- Signature Yuzu Citrus Finial seated directly on pole tip -->
          <g :transform="`translate(0 -84) rotate(${p.yuzuRock})`">
            <rect
              x="1"
              y="-13"
              width="9"
              height="4.5"
              rx="2.25"
              :fill="C.leaf"
              transform="rotate(-22 1 -11)"
            />
            <circle cx="0" cy="-2" r="8" :fill="C.yuzu" />
            <path d="M 8 -2 A 8 8 0 0 1 -3 5.4 A 10 10 0 0 1 8 -2 Z" :fill="C.yuzuShade" />
            <rect x="-4.5" y="-6.5" width="2.8" height="4.5" rx="1.4" :fill="C.white" />
          </g>
        </g>

        <!-- Prop 3: Yellow Caution Inspector Paddle (YELLOW) -->
        <g v-if="p.cautionOp > 0.01" :opacity="p.cautionOp" :transform="p.cautionTf">
          <!-- Pole -->
          <rect x="-3.5" y="-68" width="7" height="78" rx="3.5" :fill="C.feature" />
          <!-- Rounded Caution Sign Box -->
          <rect x="-20" y="-88" width="40" height="40" rx="12" :fill="C.yuzu" />
          <!-- Exclamation Mark (!) -->
          <rect x="-3" y="-79" width="6" height="16" rx="3" :fill="C.pupil" />
          <circle cx="0" cy="-56" r="3.4" :fill="C.pupil" />
          <!-- Subtle attention rays -->
          <g v-if="p.cautionPulse > 0.02" :opacity="p.cautionPulse">
            <path
              d="M 26 -78 A 18 18 0 0 1 26 -58"
              fill="none"
              :stroke="C.scanOrange"
              stroke-width="3.2"
              stroke-linecap="round"
            />
          </g>
        </g>

        <!-- Prop 4: Red Stop-Factor Traffic Light (RED) -->
        <g v-if="p.sigOp > 0.01" :opacity="p.sigOp" :transform="p.sigTf">
          <!-- Stand pole -->
          <rect x="-4" y="-32" width="8" height="46" rx="4" :fill="C.feature" />
          <!-- Traffic Light Housing -->
          <rect x="-22" y="-102" width="44" height="76" rx="17" :fill="C.housing" />
          <!-- Inactive lower lamps -->
          <circle cx="0" cy="-63" r="9.5" :fill="C.lampOff" />
          <circle cx="0" cy="-42" r="9.5" :fill="C.lampOff" />
          <!-- Active Red Top Lamp -->
          <circle cx="0" cy="-84" r="11.5" :fill="C.redLight" />
          <circle cx="-3.5" cy="-87.5" r="3.2" :fill="C.redShine" />
          <!-- Pulsing Red Warning Arcs -->
          <g
            v-for="(ring, idx) in p.redRings"
            v-show="ring.op > 0.02"
            :key="`rr${idx}`"
            :opacity="ring.op"
          >
            <path
              :d="`M ${-26 - ring.offset} -96 A 22 22 0 0 0 ${-26 - ring.offset} -70`"
              fill="none"
              :stroke="C.redGlow"
              stroke-width="3.5"
              stroke-linecap="round"
            />
            <path
              :d="`M ${26 + ring.offset} -96 A 22 22 0 0 1 ${26 + ring.offset} -70`"
              fill="none"
              :stroke="C.redGlow"
              stroke-width="3.5"
              stroke-linecap="round"
            />
          </g>
        </g>

        <!-- Paws (drawn on top of prop handles so grip reads cleanly) -->
        <rect
          :x="p.pawL.x - p.pawL.w / 2"
          :y="p.pawL.y - p.pawL.h / 2"
          :width="p.pawL.w"
          :height="p.pawL.h"
          :rx="p.pawL.h / 2"
          :fill="p.pawL.fill"
          :transform="`rotate(${p.pawL.rot} ${p.pawL.x} ${p.pawL.y})`"
        />
        <rect
          :x="p.pawR.x - p.pawR.w / 2"
          :y="p.pawR.y - p.pawR.h / 2"
          :width="p.pawR.w"
          :height="p.pawR.h"
          :rx="p.pawR.h / 2"
          :fill="p.pawR.fill"
          :transform="`rotate(${p.pawR.rot} ${p.pawR.x} ${p.pawR.y})`"
        />

        <!-- Prop 5: Floating Question Marks on OCR Error (ERROR) -->
        <g
          v-for="(q, i) in p.questions"
          v-show="q.op > 0.01"
          :key="`q${i}`"
          :opacity="q.op"
          :transform="q.tf"
        >
          <path
            d="M -5 -8 A 5.5 5.5 0 1 1 3.5 -2.5 C 1.5 -1 0 0.5 0 3"
            fill="none"
            :stroke="q.color"
            stroke-width="3.5"
            stroke-linecap="round"
          />
          <circle cx="0" cy="8.5" r="2" :fill="q.color" />
        </g>

        <!-- Zzz Glyphs (SLEEPING) -->
        <path
          v-for="(z, i) in p.zzz"
          v-show="z.op > 0.01"
          :key="`z${i}`"
          :d="z.d"
          :opacity="z.op"
          fill="none"
          :stroke="z.color"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </div>

    <!-- Clean Light Seamless Status Pill (Hero mode) -->
    <div
      v-if="!shouldHideBadge"
      class="mt-1.5 inline-flex items-center gap-2 rounded-full px-3 py-1 text-[12px] font-medium transition-colors duration-200"
      :class="{
        'bg-success-bg text-success': activeState === 'green',
        'bg-warning-bg text-warning': activeState === 'yellow',
        'bg-danger-bg text-danger': activeState === 'red' || activeState === 'error',
        'bg-accent-subtle text-accent': activeState === 'thinking' || activeState === 'peeking',
        'bg-surface-inset text-text-secondary': activeState === 'sleeping',
      }"
    >
      <span
        class="h-2 w-2 rounded-full transition-colors duration-200"
        :class="{
          'bg-success': activeState === 'green',
          'bg-warning': activeState === 'yellow',
          'bg-danger': activeState === 'red' || activeState === 'error',
          'bg-accent animate-pulse': activeState === 'thinking',
          'bg-accent': activeState === 'peeking',
          'bg-text-muted': activeState === 'sleeping',
        }"
      />
      <Transition name="yuzu-chip" mode="out-in">
        <span :key="`${activeState}-${statusLabel}`">{{ statusLabel }}</span>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.yuzu-chip-enter-active {
  transition:
    opacity 180ms cubic-bezier(0.23, 1, 0.32, 1),
    transform 180ms cubic-bezier(0.23, 1, 0.32, 1);
}
.yuzu-chip-leave-active {
  transition:
    opacity 120ms ease-in,
    transform 120ms ease-in;
}
.yuzu-chip-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.yuzu-chip-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .yuzu-chip-enter-active,
  .yuzu-chip-leave-active {
    transition: none;
  }
}
</style>
