<script setup lang="ts">
import type { CSSProperties } from 'vue'
import './Spinner.css'

withDefaults(
  defineProps<{
    size?: number
    className?: string
    class?: any
    style?: CSSProperties | any
  }>(),
  {
    size: 14,
  },
)
</script>

<template>
  <svg
    :class="['ss-spinner', className, $props.class]"
    viewBox="0 0 16 16"
    :width="size"
    :height="size"
    :style="$props.style"
    aria-hidden="true"
    v-bind="$attrs"
  >
    <circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-opacity="0.18" stroke-width="1.5" />
    <path d="M8 1.75a6.25 6.25 0 0 1 6.25 6.25" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
  </svg>
</template>
