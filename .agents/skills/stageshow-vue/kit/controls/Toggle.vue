<script setup lang="ts">
import './Toggle.css'

defineProps<{
  on: boolean
  className?: string
  class?: any
}>()
</script>

<template>
  <span
    :class="['ss-toggle', className, $props.class]"
    :data-on="on || undefined"
    role="switch"
    :aria-checked="on"
  >
    <span class="ss-toggle__knob" />
  </span>
</template>
