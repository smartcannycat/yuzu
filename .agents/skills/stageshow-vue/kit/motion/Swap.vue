<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useReducedMotion } from '../reduced-motion'
import './Swap.css'

export interface SwapProps {
  id: string | number
  duration?: number
  className?: string
  class?: any
  style?: any
}

const props = withDefaults(defineProps<SwapProps>(), {
  duration: 450,
})

const reduced = useReducedMotion()

const box = ref<HTMLSpanElement | null>(null)
const inner = ref<HTMLSpanElement | null>(null)

const prev = shallowRef<{ id: string | number; html: string; w?: number } | null>(null)
const size = ref<{ w: number; h: number } | null>(null)

const swapping = computed(() => !reduced.value && prev.value !== null)

watch(
  () => props.id,
  (newId, oldId) => {
    if (newId !== oldId) {
      if (!reduced.value && inner.value) {
        prev.value = {
          id: oldId,
          html: inner.value.innerHTML,
          w: size.value?.w,
        }
      } else {
        prev.value = null
      }
    }
  },
  { flush: 'sync' },
)

let clearTimer: ReturnType<typeof setTimeout> | null = null

watch(prev, (p) => {
  if (clearTimer) clearTimeout(clearTimer)
  if (!p) return
  if (reduced.value) {
    prev.value = null
    return
  }
  clearTimer = setTimeout(() => {
    prev.value = null
  }, props.duration)
})

function measure(observed?: boolean) {
  const b = box.value
  const el = inner.value
  if (!b || !el || (observed && swapping.value)) return
  const { width, height, transition } = b.style
  const own = { width: el.style.width, maxWidth: el.style.maxWidth }
  b.style.transition = 'none'
  b.style.width = ''
  b.style.height = ''
  el.style.width = ''
  el.style.maxWidth = ''
  const cs = getComputedStyle(el)
  const w = parseFloat(cs.width) || 0
  const h = parseFloat(cs.height) || 0
  el.style.width = own.width
  el.style.maxWidth = own.maxWidth
  b.style.width = width
  b.style.height = height
  void b.offsetWidth
  b.style.transition = transition
  if (!size.value || size.value.w !== w || size.value.h !== h) {
    size.value = { w, h }
  }
}

watch(
  () => [inner.value, props.id, reduced.value] as const,
  ([el], _, onCleanup) => {
    if (!el) return
    measure()
    const ro = new ResizeObserver(() => measure(true))
    ro.observe(el)
    onCleanup(() => ro.disconnect())
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(() => {
  if (clearTimer) clearTimeout(clearTimer)
})

const shrink = computed(() => !!(prev.value && size.value && prev.value.w !== undefined && size.value.w < prev.value.w))
const resizing = computed(() => !!(prev.value && size.value && prev.value.w !== undefined && size.value.w !== prev.value.w))

const boxStyle = computed(() => ({
  width: size.value ? `${size.value.w}px` : undefined,
  height: size.value ? `${size.value.h}px` : undefined,
  transition: !reduced.value && prev.value
    ? `width ${props.duration}ms cubic-bezier(0.25, 0.8, 0.25, 1) ${shrink.value ? Math.round(props.duration * 0.5) : 0}ms, height ${props.duration}ms cubic-bezier(0.25, 0.8, 0.25, 1)`
    : 'none',
}))

const outStyle = computed(() => ({
  animationDuration: `${props.duration * 0.5}ms`,
  width: prev.value?.w !== undefined ? `${prev.value.w}px` : undefined,
  maxWidth: prev.value?.w === undefined ? undefined : 'none',
}))

const inStyle = computed(() => ({
  animationName: reduced.value ? 'none' : undefined,
  animationDuration: `${props.duration}ms`,
  ...(!reduced.value && prev.value && size.value ? { width: `${size.value.w}px`, maxWidth: 'none' } : null),
}))
</script>

<template>
  <span
    ref="box"
    :class="['ss-swap', props.className, props.class]"
    :data-swapping="(!reduced && resizing) || undefined"
    :style="[boxStyle, props.style]"
    v-bind="$attrs"
  >
    <span
      v-if="!reduced && prev"
      :key="`p${prev.id}`"
      class="ss-swap__out"
      :style="outStyle"
      v-html="prev.html"
    />
    <span
      :key="`c${props.id}`"
      ref="inner"
      class="ss-swap__in"
      :style="inStyle"
    >
      <slot />
    </span>
  </span>
</template>
