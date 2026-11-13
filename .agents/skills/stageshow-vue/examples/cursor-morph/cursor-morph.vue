<script lang="ts">
export type MorphStyle = 'real' | 'large' | 'circle' | 'arrow'
</script>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useReducedMotion } from '../../kit'

// One outline that becomes each cursor style in turn, for the cursor picker:
// the pointer swells into the large pointer, folds into the glass circle,
// then sharpens into the solid arrowhead. Every shape is resampled to the
// same points, starting at the hotspot and running the same way round, so a
// change of style moves each point to its place in the next shape.

type Pt = [number, number]
type Look = { fill: number[]; stroke: number[]; sw: number }

const N = 72

/** Points evenly along a closed polygon, from its first vertex */
function sample(poly: Pt[], scale = 1): Pt[] {
  const p = poly.map(([x, y]) => [x * scale, y * scale] as Pt)
  const seg = p.map((a, i) => {
    const b = p[(i + 1) % p.length]
    return Math.hypot(b[0] - a[0], b[1] - a[1])
  })
  const total = seg.reduce((s, l) => s + l, 0)
  const out: Pt[] = []
  let i = 0
  let walked = 0
  for (let k = 0; k < N; k++) {
    const d = (k / N) * total
    while (walked + seg[i] < d) walked += seg[i++]
    const a = p[i]
    const b = p[(i + 1) % p.length]
    const t = seg[i] ? (d - walked) / seg[i] : 0
    out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
  }
  return out
}

// The macOS pointer, tip at the hotspot, down its left edge first
const POINTER: Pt[] = [[0, 0], [0, 16.5], [4, 12.8], [6.6, 18.6], [9.2, 17.5], [6.7, 11.8], [12, 11.8]]
// The solid arrowhead, the same way round
const HEAD: Pt[] = [[0, 0], [5.6, 15.5], [7.8, 8.8], [14.5, 6.6]]
// The glass circle about the hotspot, from its upper left, the same way round
const CIRCLE: Pt[] = Array.from({ length: N }, (_, k) => {
  const a = ((225 - (k / N) * 360) * Math.PI) / 180
  return [Math.cos(a) * 11, Math.sin(a) * 11] as Pt
})

const SHAPES: Record<MorphStyle, { pts: Pt[]; look: Look }> = {
  real: { pts: sample(POINTER), look: { fill: [0, 0, 0, 1], stroke: [255, 255, 255, 1], sw: 1.5 } },
  large: { pts: sample(POINTER, 1.5), look: { fill: [0, 0, 0, 1], stroke: [255, 255, 255, 1], sw: 2.2 } },
  circle: { pts: CIRCLE, look: { fill: [118, 118, 128, 0.34], stroke: [255, 255, 255, 0.55], sw: 0.8 } },
  arrow: { pts: sample(HEAD), look: { fill: [17, 17, 17, 1], stroke: [17, 17, 17, 1], sw: 2.6 } },
}

// A damped spring with a little overshoot, settled by about 0.5s
function spring(t: number) {
  const z = 0.62
  const w = 15
  const wd = w * Math.sqrt(1 - z * z)
  return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + ((z * w) / wd) * Math.sin(wd * t))
}

const rgba = (c: number[]) => `rgba(${c.map((v, i) => (i < 3 ? Math.round(v) : v.toFixed(3))).join(',')})`
const path = (pts: Pt[]) => `M${pts.map(([x, y]) => `${x.toFixed(2)} ${y.toFixed(2)}`).join('L')}Z`

/** Draws the morphing cursor inside the stage's own cursor, so it rides the
 * kit's movement and press. `at` is any element inside the stage. */
const props = defineProps<{
  at: HTMLElement | null
  style: MorphStyle
}>()

const host = computed(() => props.at?.closest('.ss-stage')?.querySelector<HTMLElement>('.ss-cursor') ?? null)

const pathRef = ref<SVGPathElement | null>(null)
const now = { pts: SHAPES[props.style].pts, look: SHAPES[props.style].look }
const initial = { pts: now.pts, look: now.look }
const reduced = useReducedMotion()

watch(
  () => [pathRef.value, props.style, reduced.value] as const,
  ([el, style, isReduced], _, onCleanup) => {
    const to = SHAPES[style]
    if (!el || !to) return
    if (isReduced) {
      now.pts = to.pts
      now.look = to.look
      el.setAttribute('d', path(to.pts))
      el.setAttribute('fill', rgba(to.look.fill))
      el.setAttribute('stroke', rgba(to.look.stroke))
      el.setAttribute('stroke-width', String(to.look.sw))
      return
    }
    const from = { pts: now.pts.map((p) => [...p] as Pt), look: now.look }
    const mix = (a: number, b: number, k: number) => a + (b - a) * k
    let raf = 0
    const t0 = performance.now()
    const tick = (ms: number) => {
      const t = Math.min((ms - t0) / 1000, 0.7)
      const k = t >= 0.7 ? 1 : spring(t)
      // Color and stroke don't overshoot
      const c = Math.max(0, Math.min(1, k))
      const pts = from.pts.map((p, i) => [mix(p[0], to.pts[i][0], k), mix(p[1], to.pts[i][1], k)] as Pt)
      const look = {
        fill: from.look.fill.map((v, i) => mix(v, to.look.fill[i], c)),
        stroke: from.look.stroke.map((v, i) => mix(v, to.look.stroke[i], c)),
        sw: mix(from.look.sw, to.look.sw, c),
      }
      now.pts = pts
      now.look = look
      el.setAttribute('d', path(pts))
      el.setAttribute('fill', rgba(look.fill))
      el.setAttribute('stroke', rgba(look.stroke))
      el.setAttribute('stroke-width', look.sw.toFixed(2))
      if (t < 0.7) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    onCleanup(() => cancelAnimationFrame(raf))
  },
  { flush: 'post' },
)
</script>

<template>
  <Teleport v-if="host" :to="host">
    <svg class="cm-morph" width="48" height="48" viewBox="-16 -16 48 48" aria-hidden="true">
      <path
        ref="pathRef"
        :d="path(initial.pts)"
        :fill="rgba(initial.look.fill)"
        :stroke="rgba(initial.look.stroke)"
        :stroke-width="initial.look.sw"
        stroke-linejoin="round"
      />
    </svg>
  </Teleport>
</template>
