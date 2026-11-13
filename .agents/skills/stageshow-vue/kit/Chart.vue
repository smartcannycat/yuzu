<script lang="ts">
import type { CSSProperties } from 'vue'

export interface ChartProps {
  data: number[]
  kind?: 'line' | 'bars'
  width: number
  height: number
  show?: boolean
  area?: boolean
  dot?: boolean
  max?: number
  className?: string
  class?: any
  style?: CSSProperties | any
}

export function chartPoints({
  data,
  kind = 'line',
  width,
  height,
  dot = true,
  max,
}: Pick<ChartProps, 'data' | 'kind' | 'width' | 'height' | 'dot' | 'max'>) {
  const top = max ?? Math.max(...data, 1)
  const pad = kind === 'line' && dot ? 4 : 1
  const h = height - pad * 2
  if (kind === 'bars') {
    const gap = Math.max(2, Math.round(width / data.length / 4))
    const bw = (width - gap * (data.length - 1)) / data.length
    return data.map((v, i) => ({
      x: i * (bw + gap) + bw / 2,
      y: height - Math.max(2, (v / top) * h),
    }))
  }
  return data.map((v, i) => ({
    x: pad + (i / Math.max(1, data.length - 1)) * (width - pad * 2),
    y: pad + h - (v / top) * h,
  }))
}
</script>

<script setup lang="ts">
import {
  ref,
  computed,
  useId,
  onMounted,
  watch,
} from 'vue'
import { useReducedMotion } from './reduced-motion'
import './chart.css'

const props = withDefaults(defineProps<ChartProps>(), {
  kind: 'line',
  show: true,
  area: true,
  dot: true,
})

function smooth(p: { x: number; y: number }[]) {
  if (!p.length) return ''
  let d = `M${p[0].x} ${p[0].y}`
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i - 1] ?? p[i]
    const b = p[i]
    const c = p[i + 1]
    const e = p[i + 2] ?? c
    d += `C${b.x + (c.x - a.x) / 6} ${b.y + (c.y - a.y) / 6} ${c.x - (e.x - b.x) / 6} ${c.y - (e.y - b.y) / 6} ${c.x} ${c.y}`
  }
  return d
}

const SAMPLES = 48
const DRAW_MS = 1200

function ease(t: number) {
  const b = (a: number, c: number, u: number) =>
    3 * a * u * (1 - u) ** 2 + 3 * c * u * u * (1 - u) + u ** 3
  let lo = 0
  let hi = 1
  for (let i = 0; i < 20; i++) {
    const m = (lo + hi) / 2
    if (b(0.45, 0.2, m) < t) lo = m
    else hi = m
  }
  return b(0, 1, (lo + hi) / 2)
}

function yAt(p: { x: number; y: number }[], x: number) {
  let i = 1
  while (i < p.length - 1 && p[i].x < x) i++
  const a = p[i - 1]
  const c = p[i]
  const t = c.x === a.x ? 0 : Math.max(0, Math.min(1, (x - a.x) / (c.x - a.x)))
  return a.y + (c.y - a.y) * t
}

function resample(p: { x: number; y: number }[]) {
  if (p.length < 2) return p
  const out: { x: number; y: number }[] = []
  for (let s = 0; s <= SAMPLES; s++) {
    const u = (s / SAMPLES) * (p.length - 1)
    const i = Math.min(Math.floor(u), p.length - 2)
    const t = u - i
    const a = p[i - 1] ?? p[i]
    const b = p[i]
    const c = p[i + 1]
    const e = p[i + 2] ?? c
    const c1 = { x: b.x + (c.x - a.x) / 6, y: b.y + (c.y - a.y) / 6 }
    const c2 = { x: c.x - (e.x - b.x) / 6, y: c.y - (e.y - b.y) / 6 }
    const m = 1 - t
    const k = (p0: number, p1: number, p2: number, p3: number) =>
      m * m * m * p0 + 3 * m * m * t * p1 + 3 * m * t * t * p2 + t * t * t * p3
    out.push({ x: k(b.x, c1.x, c2.x, c.x), y: k(b.y, c1.y, c2.y, c.y) })
  }
  return out
}

const reducedMotion = useReducedMotion()
const rawId = useId()
const id = computed(() => rawId.replace(/:/g, ''))

const drawRef = ref<SVGGElement | null>(null)
const wipeRef = ref<SVGRectElement | null>(null)
const dotRef = ref<SVGCircleElement | null>(null)

const top = computed(() => props.max ?? Math.max(...props.data, 1))
const pad = computed(() => (props.kind === 'line' && props.dot ? 4 : 1))
const h = computed(() => props.height - pad.value * 2)

const pts = computed(() =>
  chartPoints({
    data: props.data,
    kind: props.kind,
    width: props.width,
    height: props.height,
    dot: props.dot,
    max: props.max,
  }),
)

const curve = computed(() => resample(pts.value))
const line = computed(() => smooth(curve.value))
const fill = computed(() => {
  if (!pts.value.length) return ''
  return `${line.value}L${pts.value[pts.value.length - 1].x} ${props.height}L${pts.value[0].x} ${props.height}Z`
})
const end = computed(() => pts.value[pts.value.length - 1] ?? { x: 0, y: 0 })

let shown = false
let animRaf = 0

function runDrawIn() {
  const g = drawRef.value
  const was = shown
  shown = props.show && props.data.length > 1 && !!g
  if (!props.show || was || !g) return
  const c = dotRef.value
  const p = curve.value
  if (reducedMotion.value || p.length < 2) return
  const x0 = p[0].x
  const x1 = p[p.length - 1].x
  const wipe = wipeRef.value
  if (!wipe) return

  const at = (e: number) => {
    const x = x0 + (x1 - x0) * e
    wipe.setAttribute('width', `${x + 6}`)
    if (c) {
      c.style.setProperty('cx', `${x}px`)
      c.style.setProperty('cy', `${yAt(p, x)}px`)
    }
  }

  g.style.transition = 'opacity 0.15s ease'
  if (c) {
    c.style.transition = 'opacity 0.2s ease, transform 0.3s cubic-bezier(0.34, 1.4, 0.64, 1)'
    c.style.opacity = '1'
    c.style.transform = 'none'
  }
  at(0)
  const t0 = performance.now()
  let drawing = true

  const done = () => {
    drawing = false
    wipe.setAttribute('width', `${props.width + 12}`)
    g.style.removeProperty('transition')
    if (c) for (const k of ['cx', 'cy', 'transition', 'opacity', 'transform']) c.style.removeProperty(k)
  }

  animRaf = requestAnimationFrame(function step(now) {
    const t = Math.min(1, (now - t0) / DRAW_MS)
    at(ease(t))
    if (t < 1) animRaf = requestAnimationFrame(step)
    else done()
  })
}

onMounted(() => {
  runDrawIn()
})

watch(
  () => [props.show, props.data.length],
  () => {
    runDrawIn()
  },
)

const barMetrics = computed(() => {
  const gap = Math.max(2, Math.round(props.width / props.data.length / 4))
  const bw = (props.width - gap * (props.data.length - 1)) / props.data.length
  return { gap, bw }
})
</script>

<template>
  <svg
    v-if="!props.data.length"
    :class="['ss-chart', props.className, props.class]"
    :data-kind="props.kind"
    :data-show="props.show || undefined"
    :width="props.width"
    :height="props.height"
    :style="props.style"
    aria-hidden="true"
  />

  <svg
    v-else-if="props.kind === 'bars'"
    :class="['ss-chart', props.className, props.class]"
    data-kind="bars"
    :data-still="reducedMotion || undefined"
    :data-show="props.show || undefined"
    :width="props.width"
    :height="props.height"
    :style="props.style"
    aria-hidden="true"
  >
    <rect
      v-for="(v, i) in props.data"
      :key="i"
      class="ss-chart__bar"
      :x="i * (barMetrics.bw + barMetrics.gap)"
      :width="barMetrics.bw"
      :rx="Math.min(2, barMetrics.bw / 2)"
      :style="{
        y: `${props.height - (props.show ? Math.max(2, (v / top) * h) : 0)}px`,
        height: `${props.show ? Math.max(2, (v / top) * h) : 0}px`,
        transitionDelay: `${i * 22}ms`,
      }"
    />
  </svg>

  <svg
    v-else
    :class="['ss-chart', props.className, props.class]"
    data-kind="line"
    :data-still="reducedMotion || undefined"
    :data-show="props.show || undefined"
    :width="props.width"
    :height="props.height"
    :style="props.style"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="`${id}-fill`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="var(--ss-accent)" stop-opacity="0.18" />
        <stop offset="1" stop-color="var(--ss-accent)" stop-opacity="0" />
      </linearGradient>
      <clipPath :id="`${id}-wipe`">
        <rect ref="wipeRef" :x="-6" :y="-6" :width="props.width + 12" :height="props.height + 12" />
      </clipPath>
    </defs>
    <g ref="drawRef" class="ss-chart__draw" :clip-path="`url(#${id}-wipe)`">
      <path
        v-if="props.area && pts.length > 1"
        class="ss-chart__area"
        :d="fill"
        :style="{ d: `path('${fill}')` }"
        :fill="`url(#${id}-fill)`"
      />
      <path class="ss-chart__line" :d="line" :style="{ d: `path('${line}')` }" />
    </g>
    <circle
      v-if="props.dot"
      ref="dotRef"
      class="ss-chart__dot"
      data-lead=""
      :cx="end.x"
      :cy="end.y"
      :r="3.5"
      :style="{ cx: `${end.x}px`, cy: `${end.y}px` }"
    />
  </svg>
</template>
