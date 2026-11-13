<script setup lang="ts">
import './messages.css'

defineProps<{
  className?: string
  class?: any
}>()
</script>

<template>
  <div :class="['ss-stamp', className, $props.class]">
    <slot />
  </div>
</template>
