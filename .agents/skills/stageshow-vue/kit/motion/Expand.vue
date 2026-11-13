<script setup lang="ts">
import { computed, onMounted, ref, watch, watchPostEffect, useSlots } from 'vue'
import { useReducedMotion } from '../reduced-motion'
import type { Rect } from '../measure'
import './Expand.css'

export interface ExpandProps {
  open: boolean
  from: Rect
  radius?: number
  duration?: number
  face?: any
  class?: any
  style?: any
}

const props = withDefaults(defineProps<ExpandProps>(), {
  radius: 16,
  duration: undefined,
  face: undefined,
})

const slots = useSlots()
const refEl = ref<HTMLDivElement | null>(null)
const box = ref({ w: 0, h: 0, x: 0, y: 0, k: 1, r: 0 })

function updateBox() {
  const p = refEl.value?.parentElement
  const stage = p?.closest<HTMLElement>('.ss-stage')
  if (!p || !stage) return
  const sr = stage.getBoundingClientRect()
  const pr = p.getBoundingClientRect()
  const s = sr.width / stage.offsetWidth || 1
  const k = pr.width / p.offsetWidth || 1
  const r = parseFloat(getComputedStyle(p).getPropertyValue('--ss-screen-r')) || 0
  box.value = {
    w: p.clientWidth,
    h: p.clientHeight,
    x: (pr.left - sr.left) / s + (p.clientLeft * k) / s,
    y: (pr.top - sr.top) / s + (p.clientTop * k) / s,
    k: k / s,
    r,
  }
}

onMounted(() => {
  updateBox()
})

watch(() => [props.from?.x, props.from?.y, props.from?.width, props.from?.height], () => {
  updateBox()
})

const reduced = useReducedMotion()

const key = computed(() => {
  const f = props.from || { x: 0, y: 0, width: 0, height: 0 }
  const b = box.value
  return `${props.open}|${f.x}|${f.y}|${f.width}|${f.height}|${b.w}|${b.h}|${b.x}|${b.y}`
})

const last = ref({ open: props.open, key: key.value })
const moving = computed(() => last.value.key === key.value || last.value.open !== props.open || props.open)

watchPostEffect(() => {
  last.value = { open: props.open, key: key.value }
})

const hasFace = computed(() => !!props.face || !!slots.face)

const unmeasured = computed(() => !props.open && (!props.from?.width || !props.from?.height || !box.value.w))

const coords = computed(() => {
  const b = box.value
  const f = props.from || { x: 0, y: 0, width: 0, height: 0 }
  const x = (f.x - b.x) / b.k
  const y = (f.y - b.y) / b.k
  const w = f.width / b.k
  const h = f.height / b.k
  const r = Math.max(0, b.w - x - w)
  const bDist = Math.max(0, b.h - y - h)
  return { x, y, w, h, r, bDist }
})

const curve = computed(() => hasFace.value ? 'cubic-bezier(0.25, 0.6, 0.2, 1)' : 'cubic-bezier(0.3, 0.75, 0.1, 1)')
const ms = computed(() => reduced.value ? 0 : (props.duration ?? (hasFace.value ? 640 : 520)))
const ease = computed(() => `${ms.value}ms ${curve.value}`)

const faceStyles = computed(() => {
  const { x, y, w, h } = coords.value
  const b = box.value
  const s = b.w ? w / b.w : 1
  const clipH = Math.max(0, b.h - h / s)
  const shut = { transform: `translate(${x}px, ${y}px) scale(${s})`, clipPath: `inset(0px 0px ${clipH}px 0px round ${props.radius / s}px)` }
  const wide = { transform: 'translate(0px, 0px) scale(1)', clipPath: `inset(0px 0px 0px 0px round ${b.r}px)` }
  return {
    wrapper: {
      ...(props.open ? wide : shut),
      '--ss-expand-ms': `${ms.value}ms`,
      '--ss-expand-ease': curve.value,
      ...(moving.value ? null : { transition: 'none' }),
      ...(unmeasured.value ? { visibility: 'hidden' as const } : null),
    },
    face: {
      width: `${w}px`,
      height: `${h}px`,
      transform: `scale(${1 / s})`,
    },
  }
})

const cardStyles = computed(() => {
  const { x, y, r, bDist } = coords.value
  const b = box.value
  const clip = props.open ? `inset(0px 0px 0px 0px round ${b.r}px)` : `inset(${y}px ${r}px ${bDist}px ${x}px round ${props.radius}px)`
  const ride = {
    transform: `translate3d(0, ${props.open ? 0 : y}px, 0)`,
    transition: moving.value ? `transform ${ease.value}` : 'none',
  }
  return {
    wrapper: {
      clipPath: clip,
      transition: moving.value ? `clip-path ${ease.value}` : 'none',
      visibility: unmeasured.value ? ('hidden' as const) : undefined,
    },
    ride,
  }
})
</script>

<template>
  <div
    v-if="hasFace"
    ref="refEl"
    class="ss-expand"
    :class="props.class"
    :data-open="props.open || undefined"
    data-launch=""
    :style="[faceStyles.wrapper, props.style]"
    v-bind="$attrs"
  >
    <div class="ss-expand__content">
      <slot />
    </div>
    <div class="ss-expand__face" :style="faceStyles.face">
      <slot name="face">{{ props.face }}</slot>
    </div>
  </div>
  <div
    v-else
    ref="refEl"
    class="ss-expand"
    :class="props.class"
    :data-open="props.open || undefined"
    :style="[cardStyles.wrapper, props.style]"
    v-bind="$attrs"
  >
    <div class="ss-expand__content" :style="cardStyles.ride">
      <slot />
    </div>
  </div>
</template>
