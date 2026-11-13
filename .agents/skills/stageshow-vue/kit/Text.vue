<script setup lang="ts">
import { computed, useSlots, type CSSProperties } from 'vue'
import { useLook } from './looks'
import Bar from './Bar.vue'
import './window.css'

export interface TextProps {
  filler?: boolean
  w?: number
  h?: number
  tone?: 1 | 2 | 3 | 4 | 5
  wrap?: boolean
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<TextProps>(), {
  h: 6,
  tone: 3,
})

const slots = useSlots()
const look = useLook()

const textContent = computed(() => {
  const defaultSlot = slots.default?.()
  if (!defaultSlot || !defaultSlot.length) return ''
  const first = defaultSlot[0]
  if (typeof first.children === 'string') return first.children
  return String(first.children ?? '')
})

const isMinimal = computed(() => {
  const f = look.fidelity
  return f === 'minimal' || (props.filler && f !== 'realistic')
})

const estimatedWidth = computed(() => {
  if (props.w !== undefined) return props.w
  const str = textContent.value
  const size = typeof props.style?.fontSize === 'number' ? props.style.fontSize : 11
  return Math.round(str.length * size * 0.52)
})
</script>

<template>
  <Bar
    v-if="isMinimal"
    :w="estimatedWidth"
    :h="props.h"
    :tone="props.tone"
    :class="[props.className, props.class]"
    :style="props.style"
  />
  <span
    v-else
    :class="['ss-text', props.className, props.class]"
    :data-wrap="props.wrap || undefined"
    :style="props.style"
  >
    <slot />
  </span>
</template>
