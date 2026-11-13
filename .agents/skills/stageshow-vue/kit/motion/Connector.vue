<script setup lang="ts">
import { ref, computed, isVNode, watch, onMounted, useId } from 'vue'
import type { Point } from '../measure'
import './Connector.css'

type Route = 'h' | 'v' | 'straight' | 'step' | 'curve'

export interface ConnectorProps {
  from: Point
  to: Point
  route?: Route
  show: boolean
  radius?: number
  dots?: 'end' | 'both' | 'none'
  arrow?: boolean
  label?: any
  labelAt?: number
  dashed?: boolean
  className?: string
  class?: any
}

const props = withDefaults(defineProps<ConnectorProps>(), {
  route: 'h',
  radius: 8,
  labelAt: 0.5,
})

function isRenderableObject(v: any): boolean {
  return isVNode(v) || typeof v === 'function' || (typeof v === 'object' && v !== null)
}

function asComponent(v: any) {
  if (typeof v === 'function') return v
  if (isVNode(v) || Array.isArray(v)) return () => v
  return v
}

function bend(a: Point, b: Point): [Point, Point] {
  const m = (a.x + b.x) / 2
  return [{ x: m, y: a.y }, { x: m, y: b.y }]
}

function corners(a: Point, b: Point, route: Route): Point[] {
  if (route === 'straight') return [a, b]
  if (route === 'curve') {
    const [c1, c2] = bend(a, b)
    return Array.from({ length: 25 }, (_, i) => {
      const t = i / 24
      const u = 1 - t
      return {
        x: u * u * u * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * b.x,
        y: u * u * u * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * b.y,
      }
    })
  }
  if (route === 'step') {
    const m = (a.x + b.x) / 2
    return [a, { x: m, y: a.y }, { x: m, y: b.y }, b]
  }
  return route === 'h' ? [a, { x: b.x, y: a.y }, b] : [a, { x: a.x, y: b.y }, b]
}

function along(pts: Point[], f: number): Point {
  const segs = pts.slice(1).map((p, i) => Math.hypot(p.x - pts[i].x, p.y - pts[i].y))
  let left = segs.reduce((n, s) => n + s, 0) * Math.max(0, Math.min(1, f))
  for (let i = 0; i < segs.length; i++) {
    if (left <= segs[i] || i === segs.length - 1) {
      const t = segs[i] ? Math.min(1, left / segs[i]) : 0
      return { x: pts[i].x + (pts[i + 1].x - pts[i].x) * t, y: pts[i].y + (pts[i + 1].y - pts[i].y) * t }
    }
    left -= segs[i]
  }
  return pts[0]
}

function elbow(a: Point, b: Point, route: Route, r: number) {
  if (route === 'straight') return `M${a.x} ${a.y}L${b.x} ${b.y}`
  if (route === 'curve') {
    const [c1, c2] = bend(a, b)
    return `M${a.x} ${a.y}C${c1.x} ${c1.y} ${c2.x} ${c2.y} ${b.x} ${b.y}`
  }
  const dx = b.x - a.x
  const dy = b.y - a.y
  if (route === 'step') {
    const m = (a.x + b.x) / 2
    const k = Math.min(r, Math.abs(dx) / 2, Math.abs(dy) / 2)
    const sx = Math.sign(dx) || 1
    const sy = Math.sign(dy) || 1
    if (!k) return `M${a.x} ${a.y}H${m}V${b.y}H${b.x}`
    return `M${a.x} ${a.y}H${m - sx * k}Q${m} ${a.y} ${m} ${a.y + sy * k}V${b.y - sy * k}Q${m} ${b.y} ${m + sx * k} ${b.y}H${b.x}`
  }
  const k = Math.min(r, Math.abs(dx), Math.abs(dy))
  const sx = Math.sign(dx) || 1
  const sy = Math.sign(dy) || 1
  if (route === 'h') {
    return `M${a.x} ${a.y}H${b.x - sx * k}Q${b.x} ${a.y} ${b.x} ${a.y + sy * k}V${b.y}`
  }
  return `M${a.x} ${a.y}V${b.y - sy * k}Q${a.x} ${b.y} ${a.x + sx * k} ${b.y}H${b.x}`
}

const tip = computed(() =>
  props.arrow && props.route === 'curve'
    ? {
        x:
          props.to.x -
          Math.sign(props.to.x - props.from.x) *
            Math.min(8, Math.abs(props.to.x - props.from.x) / 3),
        y: props.to.y,
      }
    : props.to,
)

const d = computed(() =>
  tip.value === props.to
    ? elbow(props.from, props.to, props.route, props.radius)
    : `${elbow(props.from, tip.value, props.route, props.radius)}L${props.to.x} ${props.to.y}`,
)

const ends = computed(() => props.dots ?? (props.arrow ? 'none' : 'end'))

const line = ref<SVGPathElement | null>(null)
const reveal = ref<SVGPathElement | null>(null)
const rawId = useId()
const revealId = computed(() => `ss-connector-${rawId.replace(/:/g, '')}`)
const arrived = ref(false)

function setupDashes() {
  const el = line.value
  if (!el) return
  if (!props.dashed) {
    el.style.removeProperty('stroke-dasharray')
    return
  }
  const len = el.getTotalLength()
  const n = Math.max(1, Math.round((len + 4) / 8))
  const dash = (len / (n * 2 - 1)).toFixed(3)
  el.style.strokeDasharray = `${dash} ${dash}`
}

let cleanupArrived: (() => void) | null = null
function setupArrivedListener() {
  cleanupArrived?.()
  cleanupArrived = null
  const el = props.dashed ? reveal.value : line.value
  arrived.value = false
  if (!props.show || !el) return
  const check = () => {
    const style = getComputedStyle(el)
    const complete = Math.abs(parseFloat(style.strokeDashoffset)) < 0.0001
    if (complete) arrived.value = true
  }
  const settle = (event: TransitionEvent) => {
    if (event.target === el && event.propertyName === 'stroke-dashoffset') check()
  }
  el.addEventListener('transitionend', settle)
  el.addEventListener('transitioncancel', settle)
  check()
  cleanupArrived = () => {
    el.removeEventListener('transitionend', settle)
    el.removeEventListener('transitioncancel', settle)
  }
}

onMounted(() => {
  setupDashes()
  setupArrivedListener()
})

watch(() => [d.value, props.dashed], () => setupDashes(), { flush: 'post' })
watch(() => [d.value, props.dashed, props.show], () => setupArrivedListener(), { flush: 'post' })

const pts = computed(() =>
  tip.value === props.to
    ? corners(props.from, props.to, props.route)
    : [...corners(props.from, tip.value, props.route), props.to],
)

const q = computed(() => pts.value[pts.value.length - 1])
const p = computed(() => {
  const ptsArr = pts.value
  const qVal = q.value
  return (
    ptsArr
      .slice(0, -1)
      .reverse()
      .find((pt) => Math.hypot(qVal.x - pt.x, qVal.y - pt.y) > 0.001) ?? qVal
  )
})

const directionLength = computed(() => Math.hypot(q.value.x - p.value.x, q.value.y - p.value.y))
const head = computed(() => {
  const qVal = q.value
  const pVal = p.value
  const len = directionLength.value || 1
  const ux = (qVal.x - pVal.x) / len
  const uy = (qVal.y - pVal.y) / len
  return `M${qVal.x - ux * 6 - uy * 4} ${qVal.y - uy * 6 + ux * 4}L${qVal.x} ${qVal.y}L${qVal.x - ux * 6 + uy * 4} ${qVal.y - uy * 6 - ux * 4}`
})

const labelPos = computed(() => along(pts.value, props.labelAt))
</script>

<template>
  <svg
    :class="['ss-connector', props.className, props.class]"
    :data-show="props.show || undefined"
    :data-arrived="(props.show && arrived) || undefined"
    :data-dashed="props.dashed || undefined"
    aria-hidden="true"
  >
    <defs v-if="props.dashed">
      <mask :id="revealId" maskUnits="userSpaceOnUse">
        <path
          ref="reveal"
          class="ss-connector__reveal"
          :d="d"
          pathLength="1"
          style="fill: none; stroke: #fff; stroke-width: 8;"
        />
      </mask>
    </defs>
    <path
      ref="line"
      class="ss-connector__line"
      :d="d"
      :pathLength="props.dashed ? undefined : 1"
      :mask="props.dashed ? `url(#${revealId})` : undefined"
    />
    <path
      v-if="props.arrow && directionLength > 0.001"
      :d="head"
      class="ss-connector__arrow"
    />
    <circle
      v-if="ends === 'both'"
      :cx="props.from.x"
      :cy="props.from.y"
      r="3"
      class="ss-connector__dot ss-connector__dot--start"
    />
    <circle
      v-if="ends !== 'none'"
      :cx="props.to.x"
      :cy="props.to.y"
      r="3"
      class="ss-connector__dot"
    />
  </svg>

  <span
    v-if="props.label !== undefined || $slots.label"
    class="ss-connector__label"
    :data-show="props.show || undefined"
    :data-arrived="(props.show && arrived) || undefined"
    :data-step="typeof props.label === 'number' || undefined"
    :style="{ left: `${labelPos.x}px`, top: `${labelPos.y}px` }"
  >
    <slot name="label">
      <component :is="asComponent(props.label)" v-if="isRenderableObject(props.label)" />
      <template v-else>{{ props.label }}</template>
    </slot>
  </span>
</template>
