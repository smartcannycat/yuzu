<script setup lang="ts">
import { computed, useSlots } from 'vue'
import { useReducedMotion } from '../reduced-motion'
import './States.css'

export interface StatesProps {
  value: string
  states?: Record<string, any>
  /** Where a smaller state sits in the box: start for text in a row, center for a button's label, end for a right-aligned value. */
  align?: 'start' | 'center' | 'end'
  class?: any
  style?: any
}

const props = withDefaults(defineProps<StatesProps>(), {
  align: 'center',
  states: () => ({}),
})

const slots = useSlots()
const reduced = useReducedMotion()

const stateKeys = computed(() => {
  const set = new Set<string>()
  if (props.states) {
    for (const k of Object.keys(props.states)) set.add(k)
  }
  for (const k of Object.keys(slots)) {
    if (k !== 'default') set.add(k)
  }
  return Array.from(set)
})
</script>

<template>
  <span
    class="ss-states"
    :class="props.class"
    :data-align="props.align"
    :data-reduced="reduced || undefined"
    :style="props.style"
    v-bind="$attrs"
  >
    <span
      v-for="k in stateKeys"
      :key="k"
      class="ss-states__item"
      :data-on="k === props.value || undefined"
      :aria-hidden="k !== props.value || undefined"
    >
      <slot :name="k">{{ props.states?.[k] }}</slot>
    </span>
  </span>
</template>
