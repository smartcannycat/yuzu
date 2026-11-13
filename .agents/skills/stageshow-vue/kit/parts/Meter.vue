<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import './Meter.css'

export interface MeterProps {
  value: number
  tone?: 'accent' | 'danger' | 'warning' | 'success' | 'ink'
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<MeterProps>(), {
  tone: 'accent',
})

const fillStyle = computed(() => {
  const v = Math.max(0, Math.min(1, props.value))
  return {
    clipPath: `inset(0 ${(1 - v) * 100}% 0 0 round 3px)`,
  }
})
</script>

<template>
  <span
    :class="['ss-meter', props.className, props.class]"
    :data-tone="props.tone"
    :style="props.style"
    v-bind="$attrs"
  >
    <span class="ss-meter__fill" :style="fillStyle" />
  </span>
</template>
