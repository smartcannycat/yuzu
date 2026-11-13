<script setup lang="ts" generic="S extends object = any">
import {
  ref,
  computed,
  watch,
  onMounted,
  onUpdated,
  onUnmounted,
  type CSSProperties,
  type VNode,
} from 'vue'
import './stage.css'
import { checkSeam, createAct, Stopped, type Script } from './act'
import { Cursor, ripple as spawnRipple, type CursorKind, type CursorStyle } from './cursor'
import { Keycaps, type Keys, type KeysAt } from './keys'
import { provideLook, type Fidelity, type Layout, type Palette, type Theme, type Look } from './looks'
import { EMPTY, nameOf, rectOf, sameRects, stageSpace, targetRectOf, thumb, type Point, type Rect, type Target } from './measure'
import { provideStill, useReducedMotion } from './reduced-motion'
import { clock } from './clock'
import { clamp, easeInOutCubic, isDev, warn } from './util'

export type Play = 'loop' | 'once' | 'hover'
export type LookTokens = { [token: `--ss-${string}`]: string }

export interface StageProps<S = any> {
  width: number
  height: number
  initial?: S
  script?: Script<S>
  poster?: S
  cursor?: {
    at: Target | { wide: Target; compact: Target }
    kind?: CursorKind
    style?: CursorStyle
    still?: boolean
    ripple?: boolean
    idle?: number | false
  }
  play?: Play
  compact?: { below: number; width: number; height: number }
  keys?: KeysAt | { wide: KeysAt; compact: KeysAt }
  hover?: string[]
  theme?: Theme
  palette?: Palette
  fidelity?: Fidelity
  greys?: 'warm' | 'cool'
  tokens?: LookTokens
  fill?: boolean
  accent?: string
  ground?: 'orbs' | [string, string] | [string, string, string]
  speed?: number
  className?: string
  class?: any
  style?: any
  specimen?: boolean
  unframed?: boolean
  children?: (s: S, rect: (name: string) => Rect, layout: Layout) => VNode | VNode[] | any
}

const props = withDefaults(defineProps<StageProps<S>>(), {
  initial: () => ({} as any),
  play: 'loop',
  keys: 'bottom',
  palette: 'accent',
  fidelity: 'standard',
  speed: 1,
  fill: false,
  theme: 'light',
})

defineSlots<{
  default?: (props: { state: S; rect: (name: string) => Rect; layout: Layout }) => any
}>()

function cloneState<T>(s: T): T {
  if (s && typeof s === 'object' && !Array.isArray(s)) return { ...s }
  return s
}

const reducedMotion = useReducedMotion()
const still = computed(() => !props.script || reducedMotion.value)
provideStill(still)

const play = computed<Play>(() => {
  if (props.play === 'hover' && typeof window !== 'undefined' && window.matchMedia('(hover: none)').matches) {
    return 'once'
  }
  return props.play
})

const layout = ref<Layout>('wide')
const grows = ref(false)
const designW = computed(() => (layout.value === 'compact' && props.compact ? props.compact.width : props.width))
const designH = computed(() => (layout.value === 'compact' && props.compact ? props.compact.height : props.height))

const fitRef = ref<HTMLDivElement | null>(null)
const rootRef = ref<HTMLDivElement | null>(null)
const cursorRef = ref<HTMLDivElement | null>(null)

const state = ref<any>(cloneState(still.value && props.poster ? props.poster : props.initial))
const scale = ref(1)
const inset = ref(0)

const film = typeof window === 'undefined' ? {} : ((window as unknown as { __stageshow?: { slow?: number; theme?: Theme } }).__stageshow ?? {})
const effectiveSpeed = computed(() => props.speed / (film.slow ?? 1))
const effectiveTheme = computed(() => film.theme ?? props.theme)

const kind = ref<CursorKind>(props.cursor?.kind ?? 'pointer')
const keysState = ref<Keys>({ id: 0, caps: [], show: false, down: false })
const lastKeys = ref<Keys | null>(null)

const pos = ref<Point>({ x: 0, y: 0 })
const autoRef = ref<((p: Point) => void) | null>(null)
const autoUsed = ref(false)
const dragging = ref(false)
const hovered = ref<Element | null>(null)
const settling = ref(true)

const look = computed<Look>(() => ({
  theme: effectiveTheme.value,
  palette: props.palette,
  fidelity: props.fidelity,
  layout: layout.value,
}))
provideLook(look)

function restAt(): Target {
  const at = props.cursor!.at
  return typeof at === 'object' && 'wide' in at ? at[layout.value] : at
}

function ripple(at: Point) {
  const root = rootRef.value
  if (!root || reducedMotion.value) return
  spawnRipple(root, at)
}

function resolve(t: Target): Point {
  if (typeof t === 'object' && t !== null && 'wide' in t) {
    t = layout.value === 'compact' ? t.compact : t.wide
  }
  const name = nameOf(t)
  if (name === null) return t as Point
  const root = rootRef.value
  const el = root?.querySelector<HTMLElement>(`[data-target="${name}"]`)
  if (!root || !el) {
    warn(`no element with data-target="${name}"`)
    return pos.value
  }
  const r = rectOf(root, el, scale.value)
  const f = typeof t === 'string' ? { x: 0.5, y: 0.5 } : (t as { x: number; y: number })
  return { x: r.x + r.width * f.x, y: r.y + r.height * f.y }
}

const active = ref(0)
const loopAt = ref(0)
const moved = ref(false)
const firstMove = ref<number | null>(null)

function place(p: Point) {
  if (loopAt.value && !moved.value && Math.hypot(p.x - pos.value.x, p.y - pos.value.y) > 0.5) {
    moved.value = true
    if (firstMove.value === null) {
      firstMove.value = performance.now() - loopAt.value
    }
  }
  pos.value = p
  active.value = performance.now()
  const el = cursorRef.value
  if (!el) return
  el.style.transform = `translate(${p.x}px, ${p.y}px)`
  el.removeAttribute('data-idle')
}

// Measurement & Rects
const rects = ref<Record<string, Rect>>({})
function measureAll(): Record<string, Rect> {
  const root = rootRef.value
  if (!root) return {}
  const out: Record<string, Rect> = {}
  const targets = root.querySelectorAll<HTMLElement>('[data-target]')
  if (!targets.length) return out
  const space = stageSpace(root, scale.value)
  targets.forEach((el) => {
    out[el.dataset.target!] = targetRectOf(root, el, scale.value, space)
  })
  return out
}

const passes = { n: 0, frame: 0, owed: false }
function remeasure() {
  if (!passes.frame) {
    passes.frame = clock.layoutRaf(() => {
      passes.n = 0
      passes.frame = 0
      if (!passes.owed) return
      passes.owed = false
      const next = measureAll()
      if (!sameRects(rects.value, next)) rects.value = next
    })
  }
  if (passes.n >= 4) {
    passes.owed = true
    return
  }
  passes.n++
  const next = measureAll()
  if (!sameRects(rects.value, next)) rects.value = next
}

function rectFor(name: string): Rect {
  return rects.value[name] ?? EMPTY
}

function applyStillHover() {
  if (!still.value || !props.hover) return
  const root = rootRef.value
  if (!root) return
  props.hover.forEach((name) => root.querySelector(`[data-target="${name}"]`)?.setAttribute('data-hover', ''))
}

// Layout measurement
function updateFit() {
  const fit = fitRef.value
  if (!fit) return
  const w = fit.clientWidth
  const wide = !!fit.parentElement?.closest('[data-ss-wide]')
  const next: Layout = props.compact && !wide && w < props.compact.below ? 'compact' : 'wide'
  layout.value = next
  const grow = props.fill || !!fit.parentElement?.closest('[data-ss-fill]')
  grows.value = grow
  const dw = next === 'compact' ? props.compact!.width : props.width
  const s = Math.min(grow ? 2 : 1, w / dw)
  scale.value = s
  inset.value = Math.max(0, (w - dw * s) / 2)
  if (isMounted) remeasure()
}

// Settling on mount and layout switch
let settleFrameId = 0
let isMounted = false
function startSettling() {
  clock.cancelLayoutRaf(settleFrameId)
  settling.value = true
  const releasePlacing = () => {
    settleFrameId = clock.layoutRaf(() => {
      settleFrameId = clock.layoutRaf(() => {
        if (isMounted) settling.value = false
      })
    })
  }
  if (typeof document === 'undefined' || !document.fonts || document.fonts.status === 'loaded') {
    releasePlacing()
  } else {
    document.fonts.ready.then(() => {
      if (isMounted) releasePlacing()
    })
  }
}

// Reset loop
const glideId = ref(0)
let resetFrame = 0
function cancelReset() {
  glideId.value++
  cancelAnimationFrame(resetFrame)
  resetFrame = 0
  rootRef.value?.removeAttribute('data-settling')
}

function reset(glide = false) {
  cancelReset()
  const id = glideId.value
  dragging.value = false
  state.value = cloneState(props.initial)
  kind.value = props.cursor?.kind ?? 'pointer'
  keysState.value = { ...keysState.value, show: false, down: false }
  lastKeys.value = null

  const root = rootRef.value
  if (root) {
    root.querySelectorAll('[data-hover],[data-pressed]').forEach((el) => {
      el.removeAttribute('data-hover')
      el.removeAttribute('data-pressed')
    })
    root.removeAttribute('data-mark')
    root.querySelectorAll<HTMLElement>('[data-scrolled]').forEach((el) => {
      el.scrollTop = 0
      el.removeAttribute('data-scrolled')
      thumb(el)
    })
    root.querySelectorAll('[data-scrolling]').forEach((el) => el.removeAttribute('data-scrolling'))
  }
  cursorRef.value?.removeAttribute('data-pressed')
  hovered.value = null
  applyStillHover()

  if (!props.cursor) return
  if (!glide) {
    resetFrame = requestAnimationFrame(() => {
      resetFrame = 0
      place(resolve(restAt()))
      autoRef.value?.(pos.value)
    })
    return
  }

  root?.setAttribute('data-settling', '')
  resetFrame = requestAnimationFrame(() => {
    const from = { ...pos.value }
    const end = resolve(restAt())
    const ms = clamp(320 + Math.hypot(end.x - from.x, end.y - from.y) * 0.7, 380, 700)
    const t0 = performance.now()
    const step = () => {
      if (glideId.value !== id) return
      const t = Math.min(1, (performance.now() - t0) / ms)
      const e = easeInOutCubic(t)
      place({ x: from.x + (end.x - from.x) * e, y: from.y + (end.y - from.y) * e })
      if (t < 1) {
        resetFrame = requestAnimationFrame(step)
      } else {
        resetFrame = 0
        root?.removeAttribute('data-settling')
      }
    }
    step()
  })
}

// Script Act runner
function makeAct(signal: AbortSignal) {
  return createAct(signal, {
    rootRef,
    cursorRef,
    pos,
    hovered,
    kindRef: kind,
    keysRef: keysState,
    dragging,
    autoUsed,
    autoRef,
    scaleRef: scale,
    speed: effectiveSpeed.value,
    layout: layout.value,
    cursor: props.cursor,
    resolve,
    place,
    remeasure,
    ripple,
    setState: (patch) => {
      state.value = {
        ...state.value,
        ...(typeof patch === 'function' ? (patch as any)(state.value) : patch),
      }
    },
    setKind: (k) => {
      kind.value = k
    },
    setKeys: (k) => {
      keysState.value = typeof k === 'function' ? k(keysState.value) : k
    },
    setLastKeys: (k) => {
      lastKeys.value = k
    },
  })
}

let scriptCtrl: AbortController | null = null
let idleTimer = 0
let revealTimer = 0

function watchIdle() {
  window.clearInterval(idleTimer)
  const idle = props.cursor?.idle ?? 4000
  if (!props.cursor || idle === false) return
  active.value = performance.now()
  const LEAD = 1200
  idleTimer = window.setInterval(() => {
    const el = cursorRef.value
    if (!el) return
    const now = performance.now()
    if (!moved.value) {
      if (firstMove.value === null && now - active.value > LEAD) el.setAttribute('data-idle', '')
      return
    }
    if (el.hasAttribute('data-pressed') || rootRef.value?.querySelector('[data-hover]')) {
      active.value = now
    } else if (now - active.value > idle) {
      el.setAttribute('data-idle', '')
    }
  }, 150)
}

function beginLoop() {
  loopAt.value = performance.now()
  moved.value = false
  window.clearTimeout(revealTimer)
  const el = cursorRef.value
  const waitTime = firstMove.value
  const idle = props.cursor?.idle ?? 4000
  const LEAD = 1200
  if (idle === false || !el || waitTime === null || waitTime <= LEAD) return
  el.setAttribute('data-idle', '')
  revealTimer = window.setTimeout(() => el.removeAttribute('data-idle'), waitTime - 400)
}

function unwatchIdle() {
  window.clearInterval(idleTimer)
  window.clearTimeout(revealTimer)
  loopAt.value = 0
  cursorRef.value?.removeAttribute('data-idle')
}

function finishIdle() {
  window.clearInterval(idleTimer)
  window.clearTimeout(revealTimer)
  const el = cursorRef.value
  const held = () => el?.hasAttribute('data-pressed') || rootRef.value?.querySelector('[data-hover]')
  const idle = props.cursor?.idle ?? 4000
  const LEAD = 1200
  if (!props.cursor || idle === false || !el || el.hasAttribute('data-idle') || held()) return
  const delay = (moved.value ? idle : LEAD) - (performance.now() - active.value)
  revealTimer = window.setTimeout(() => {
    if (!held()) el.setAttribute('data-idle', '')
  }, Math.max(0, delay))
}

let onScreen = false
let hovering = false
let scriptDone = false

function startScript() {
  if (still.value || !props.script) return
  if (scriptCtrl || scriptDone || !onScreen || (typeof document !== 'undefined' && document.hidden)) return
  if (play.value === 'hover' && !hovering) return
  cancelReset()
  if (props.cursor) place(resolve(restAt()))
  scriptCtrl = new AbortController()
  const signal = scriptCtrl.signal
  watchIdle()
  const act = makeAct(signal)
  ;(async () => {
    do {
      beginLoop()
      try {
        if (props.script) await props.script(act)
      } catch (e) {
        if (e instanceof Stopped) return
        console.error('[stageshow] script error', e)
        scriptCtrl = null
        unwatchIdle()
        return
      }
      if (play.value === 'loop' && isDev()) {
        checkSeam(state.value as object, (props.initial ?? {}) as object, pos.value, props.cursor ? resolve(restAt()) : null)
      }
    } while (play.value === 'loop' && !signal.aborted)

    if (play.value === 'once' && !signal.aborted) {
      scriptDone = true
      finishIdle()
    }
  })()
}

function stopScript(glide = false) {
  unwatchIdle()
  if (!scriptCtrl) return
  scriptCtrl.abort()
  scriptCtrl = null
  if (!scriptDone) reset(glide)
}

// Lifecycle hooks
let ro: ResizeObserver | null = null
let hostsObserver: MutationObserver | null = null
let io: IntersectionObserver | null = null

onMounted(() => {
  isMounted = true
  const fit = fitRef.value
  const root = rootRef.value
  if (!fit || !root) return

  updateFit()
  ro = new ResizeObserver(updateFit)
  ro.observe(fit)

  hostsObserver = new MutationObserver(updateFit)
  for (let host = fit.parentElement; host; host = host.parentElement) {
    hostsObserver.observe(host, { attributes: true, attributeFilter: ['data-ss-wide', 'data-ss-fill'] })
  }

  // Transitions remeasure
  root.addEventListener('transitionend', remeasure)
  root.addEventListener('animationend', remeasure)

  startSettling()
  applyStillHover()

  // Cursor initial placement
  if (props.cursor && !loopAt.value) {
    place(resolve(restAt()))
  }

  // Intersection & Visibility
  const markOffscreen = () => root.toggleAttribute('data-offscreen', !still.value && (!onScreen || document.hidden))
  markOffscreen()

  io = new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting
    markOffscreen()
    onScreen ? startScript() : stopScript()
  })
  io.observe(fit)

  const onVisibility = () => {
    markOffscreen()
    document.hidden ? stopScript() : startScript()
  }
  document.addEventListener('visibilitychange', onVisibility)

  const onEnter = () => {
    hovering = true
    startScript()
  }
  const onLeave = () => {
    hovering = false
    stopScript(true)
  }
  if (play.value === 'hover') {
    fit.addEventListener('pointerenter', onEnter)
    fit.addEventListener('pointerleave', onLeave)
  }

  remeasure()

  onUnmounted(() => {
    isMounted = false
    clock.cancelLayoutRaf(settleFrameId)
    clock.cancelLayoutRaf(passes.frame)
    ro?.disconnect()
    hostsObserver?.disconnect()
    io?.disconnect()
    document.removeEventListener('visibilitychange', onVisibility)
    fit.removeEventListener('pointerenter', onEnter)
    fit.removeEventListener('pointerleave', onLeave)
    root.removeEventListener('transitionend', remeasure)
    root.removeEventListener('animationend', remeasure)
    stopScript()
    cancelReset()
  })
})

onUpdated(() => {
  remeasure()
  applyStillHover()
})

watch(
  () => [props.width, props.compact?.below, props.compact?.width, props.fill],
  () => updateFit(),
  { flush: 'post' },
)

watch(
  () => layout.value,
  () => startSettling(),
  { flush: 'post' },
)

watch(
  () => [scale.value, layout.value],
  () => {
    if (props.cursor && !loopAt.value) {
      place(resolve(restAt()))
    }
  },
  { flush: 'post' },
)

watch(
  () => [still.value, props.script, play.value, layout.value],
  () => {
    stopScript()
    scriptDone = false
    if (still.value || !props.script) {
      reset()
      rootRef.value?.removeAttribute('data-offscreen')
      state.value = cloneState(props.poster ?? props.initial)
      applyStillHover()
    } else {
      reset()
      startScript()
    }
  },
  { flush: 'post' },
)

watch(
  () => state.value,
  () => {
    if (props.cursor && !still.value && !dragging.value) {
      autoRef.value?.(pos.value)
    }
    remeasure()
  },
  { deep: true, flush: 'post' },
)

const showCursor = computed(() => props.cursor && (!props.script || !still.value || props.cursor.still))
const keysLocation = computed(() => {
  if (typeof props.keys === 'string') return props.keys
  return props.keys[layout.value]
})

const fitStyle = computed<CSSProperties>(() => ({
  maxWidth: grows.value ? undefined : `${props.width}px`,
  height: `${designH.value * scale.value}px`,
}))

const groundStyle = computed<CSSProperties | undefined>(() => {
  if (!props.ground) return undefined
  if (Array.isArray(props.ground)) {
    return {
      '--ss-orb-1': props.ground[0],
      '--ss-orb-2': props.ground[1],
      ...(props.ground[2] ? { '--ss-orb-3': props.ground[2] } : null),
    } as CSSProperties
  }
  return undefined
})

const stageStyle = computed<CSSProperties>(() => ({
  width: `${designW.value}px`,
  height: `${designH.value}px`,
  marginLeft: inset.value ? `${inset.value}px` : undefined,
  transform: `scale(${scale.value})`,
  ...props.tokens,
  ...(props.accent
    ? {
        '--ss-accent': props.accent,
        '--ss-accent-2': props.accent,
        '--ss-accent-soft': `color-mix(in srgb, ${props.accent} 14%, transparent)`,
      }
    : null),
  ...props.style,
}))
</script>

<template>
  <div ref="fitRef" :class="['ss-fit', props.className, props.class]" :style="fitStyle">
    <div
      ref="rootRef"
      class="ss-stage"
      :data-specimen="props.specimen || undefined"
      :data-unframed="props.unframed || undefined"
      :data-still="still || undefined"
      :data-placing="settling || undefined"
      :data-theme="effectiveTheme"
      :data-palette="props.palette"
      :data-greys="props.greys === 'cool' ? 'cool' : undefined"
      :data-fidelity="props.fidelity"
      :data-layout="layout"
      :style="stageStyle"
    >
      <div v-if="props.ground" class="ss-ground" aria-hidden="true" :style="groundStyle" />
      <slot :state="state" :rect="rectFor" :layout="layout">
        <component
          v-if="props.children"
          :is="() => props.children!(state, rectFor, layout)"
        />
      </slot>
      <Keycaps
        v-if="Boolean(props.script)"
        :rows="[lastKeys, keysState]"
        :at="keysLocation"
      />
      <Cursor
        v-if="showCursor"
        :ref="(c: any) => (cursorRef = c?.el ?? c?.$el ?? c)"
        :cursor-style="props.cursor?.style"
        :kind="kind"
      />
    </div>
  </div>
</template>
