<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import { useReducedMotion } from '../reduced-motion'
import type { Rect } from '../measure'
import { warn } from '../util'
import './Fly.css'

export interface FlyProps {
  /** Where it starts and where it lands, in stage pixels (from `rect()`): the source element's own rect and the landing element's own rect, never a slot or wrapper around them. */
  from: Rect
  to: Rect
  /** False waits at `from`, hidden; true shows it there and flies to `to`. Hide the source in the same set that turns it true. */
  go: boolean
  /** Shown while it waits at `from`: the thing being carried (under the cursor, before it flies), or a chip budding off a value, which grows out of it (it scales up from the source as it fades in) rather than popping in whole. Off by default, so it never doubles the element it leaves. */
  held?: boolean
  /** ms for the flight. Default 750. */
  duration?: number
  class?: any
  style?: any
}

const props = withDefaults(defineProps<FlyProps>(), {
  held: false,
  duration: 750,
})

const reduced = useReducedMotion()

const heldState = ref<{ from: Rect; to: Rect } | null>(null)

watch(() => props.go, (go) => {
  if (!go) {
    heldState.value = null
  } else if (!heldState.value) {
    heldState.value = { from: props.from, to: props.to }
  }
}, { immediate: true })

const start = computed(() => heldState.value?.from ?? props.from)
const target = computed(() => heldState.value?.to ?? props.to)
const from = computed(() => start.value.width ? start.value : { ...start.value, width: target.value.width || 1, height: target.value.height || 1 })
const at = computed(() => props.go ? target.value : from.value)
const ms = computed(() => reduced.value ? 0 : props.duration)
const sx = computed(() => at.value.width / (from.value.width || 1))

const body = ref<HTMLDivElement | null>(null)

watchEffect(() => {
  const el = body.value?.firstElementChild as HTMLElement | null
  if (!el || !start.value.width) return
  if (Math.abs(el.offsetWidth - from.value.width) > 1 || Math.abs(el.offsetHeight - from.value.height) > 1) {
    warn(`Fly: the child is ${el.offsetWidth}×${el.offsetHeight} but takes off from ${Math.round(from.value.width)}×${Math.round(from.value.height)}. Draw it at the start size, and pass the landing element's own rect as \`to\`.`)
  }
})
</script>

<template>
  <div
    class="ss-fly"
    :class="props.class"
    :data-go="props.go || undefined"
    :data-held="props.held || undefined"
    :style="[
      {
        visibility: props.go || props.held ? undefined : 'hidden',
        left: `${from.x}px`,
        top: `${from.y}px`,
        width: `${from.width}px`,
        height: `${from.height}px`,
        transform: `translateX(${at.x - from.x}px)`,
        transition: `transform ${ms}ms cubic-bezier(0.35, 0, 0.2, 1)`,
      },
      props.style,
    ]"
    v-bind="$attrs"
  >
    <div
      :style="{
        transform: `translateY(${at.y - from.y}px) scale(${sx})`,
        transformOrigin: '0 0',
        transition: `transform ${ms}ms cubic-bezier(0.3, 0.6, 0.15, 1)`,
      }"
    >
      <div
        ref="body"
        class="ss-fly__lift"
        :style="props.go ? { animationDuration: `${ms}ms` } : undefined"
      >
        <slot />
      </div>
    </div>
  </div>
</template>
