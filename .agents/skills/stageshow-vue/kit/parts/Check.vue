<script setup lang="ts">
import './Check.css'

withDefaults(
  defineProps<{
    on: boolean
    pending?: boolean
    size?: number
    className?: string
    class?: any
  }>(),
  {
    size: 16,
  },
)
</script>

<template>
  <span
    :class="['ss-check', className, $props.class]"
    :data-on="on || undefined"
    :data-pending="(pending && !on) || undefined"
    :style="{ width: `${size}px`, height: `${size}px` }"
    v-bind="$attrs"
  >
    <svg viewBox="0 0 16 16" :width="size" :height="size" aria-hidden="true">
      <circle class="ss-check__ring" cx="8" cy="8" r="7.25" />
      <circle class="ss-check__arc" cx="8" cy="8" r="7.25" pathLength="1" />
      <circle class="ss-check__fill" cx="8" cy="8" r="8" />
      <path class="ss-check__tick" d="M4.5 8.2 7 10.6l4.6-5" pathLength="1" />
    </svg>
  </span>
</template>
