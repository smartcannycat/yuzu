<script lang="ts">
/**
 * Which cell a value falls in, sticky at the borders: it only changes once
 * the value is `hysteresis` of a cell past the edge, so a drag along a border
 * doesn't flicker between two cells.
 */
export function cellOf(value: number, size: number, prev: number | null, hysteresis = 0.2) {
  const raw = Math.floor(value / size)
  if (prev === null || raw === prev) return raw
  const edge = raw > prev ? (prev + 1) * size : prev * size
  return Math.abs(value - edge) > size * hysteresis ? raw : prev
}
</script>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Rect } from '../measure'
import { useReducedMotion } from '../reduced-motion'
import './Follow.css'

export interface FollowProps {
  /** The rect to sit on, in stage pixels. null hides it. */
  to: Rect | null
  /** Higher is snappier. 0.25 is a quick, settled follow. */
  stiffness?: number
  className?: string
  class?: any
  style?: any
}

const props = withDefaults(defineProps<FollowProps>(), {
  stiffness: 0.25,
})

const reduced = useReducedMotion()
const el = ref<HTMLDivElement | null>(null)
const cur = ref<Rect | null>(null)
const vel = ref({ x: 0, y: 0, width: 0, height: 0 })

let id = 0
let running = false
const keys = ['x', 'y', 'width', 'height'] as const
let previous = performance.now()
let remainder = 0
let simulation: Rect | null = null
let velocity = { x: 0, y: 0, width: 0, height: 0 }
let priorTarget: Rect | null = null

function integrate(c: Rect, v: typeof velocity, t: Rect, k: number, damp: number) {
  for (const key of keys) {
    v[key] += (t[key] - c[key]) * k - v[key] * damp
    c[key] += v[key]
  }
}

function step(time = performance.now()) {
  const elapsed = Math.min(100, Math.max(0, time - previous))
  previous = time
  const t = props.to
  const node = el.value

  if (!t || reduced.value) {
    cur.value = t ? { ...t } : null
    vel.value = { x: 0, y: 0, width: 0, height: 0 }
    simulation = cur.value ? { ...cur.value } : null
    velocity = { ...vel.value }
    remainder = 0
  }

  if (node && t) {
    if (!cur.value) cur.value = { ...t }
    if (!simulation || !priorTarget || keys.some(key => priorTarget![key] !== t[key])) {
      simulation = { ...cur.value }
      velocity = { ...vel.value }
      remainder = 0
    }
    priorTarget = { ...t }
    const c = cur.value
    const v = vel.value
    const k = props.stiffness
    const damp = 2 * Math.sqrt(k) * 0.95
    const frame = 1000 / 60

    remainder += elapsed
    while (remainder >= frame - 1e-6) {
      integrate(simulation, velocity, t, k, damp)
      remainder = Math.max(0, remainder - frame)
    }
    const next = { ...simulation }
    const nextVelocity = { ...velocity }
    integrate(next, nextVelocity, t, k, damp)
    const part = remainder / frame
    for (const key of keys) {
      c[key] = simulation[key] + (next[key] - simulation[key]) * part
      v[key] = velocity[key] + (nextVelocity[key] - velocity[key]) * part
      if (Math.abs(t[key] - c[key]) < 0.05 && Math.abs(v[key]) < 0.05) {
        c[key] = t[key]
        v[key] = 0
      }
    }
    node.style.transform = `translate(${c.x}px, ${c.y}px)`
    node.style.width = `${c.width}px`
    node.style.height = `${c.height}px`
  }

  const c = cur.value
  const v = vel.value
  const settled = !t || !node || (c !== null && v.x === 0 && v.y === 0 && v.width === 0 && v.height === 0 && c.x === t.x && c.y === t.y && c.width === t.width && c.height === t.height)
  running = !settled
  if (running) {
    id = requestAnimationFrame(step)
  }
}

function wake() {
  if (reduced.value || !props.to || !cur.value) {
    cancelAnimationFrame(id)
    running = false
    step()
    return
  }
  if (running || (cur.value && keys.every(key => cur.value![key] === props.to![key] && vel.value[key] === 0))) return
  running = true
  previous = performance.now()
  id = requestAnimationFrame(step)
}

onMounted(() => {
  wake()
})

onBeforeUnmount(() => {
  running = false
  cancelAnimationFrame(id)
})

watch(() => [props.to?.x, props.to?.y, props.to?.width, props.to?.height, !props.to], () => {
  wake()
}, { flush: 'post' })

watch(() => [props.stiffness, reduced.value], () => {
  wake()
}, { flush: 'post' })
</script>

<template>
  <div
    ref="el"
    :class="['ss-follow', props.className, props.class]"
    :data-show="props.to ? true : undefined"
    :style="[props.style, reduced ? { transition: 'none' } : null]"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>
