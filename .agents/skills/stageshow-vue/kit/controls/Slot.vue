<script setup lang="ts">
import type { CSSProperties } from 'vue'
import './Slot.css'

export interface SlotProps {
  open: boolean
  height: number
  gap?: number
  dashed?: boolean
  className?: string
  class?: any
  style?: CSSProperties | any
}

withDefaults(defineProps<SlotProps>(), {
  gap: 0,
})
</script>

<template>
  <div
    :class="['ss-slot', className, $props.class]"
    :data-open="open || undefined"
    :data-dashed="dashed || undefined"
    :style="{
      height: open ? `${height}px` : '0px',
      marginTop: open ? '0px' : `${-gap}px`,
      ...$props.style,
    }"
  >
    <div class="ss-slot__clip">
      <div class="ss-slot__mark" :style="{ height: `${height}px` }" />
    </div>
    <slot />
  </div>
</template>
