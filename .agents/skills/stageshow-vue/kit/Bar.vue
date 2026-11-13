<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import './window.css'

export interface BarProps {
  w: number | string
  h?: number
  tone?: 1 | 2 | 3 | 4 | 5
  r?: number
  shrink?: boolean
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<BarProps>(), {
  h: 6,
  tone: 3,
  r: 2,
})

const INK = ['var(--ss-ink-1)', 'var(--ss-ink-2)', 'var(--ss-ink-3)', 'var(--ss-ink-4)', 'var(--ss-ink-5)']

const gives = computed(() => props.shrink ?? (typeof props.w === 'number' && props.w > props.h * 3))

const barStyle = computed(() => ({
  width: typeof props.w === 'number' ? `${props.w}px` : props.w,
  height: `${props.h}px`,
  borderRadius: `${props.r}px`,
  background: INK[props.tone - 1],
  ...props.style,
}))
</script>

<template>
  <span
    :class="['ss-bar', props.className, props.class]"
    :data-shrink="gives || undefined"
    :style="barStyle"
  />
</template>
