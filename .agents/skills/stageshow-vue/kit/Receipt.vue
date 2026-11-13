<script setup lang="ts">
import Roll from './motion/Roll.vue'
import './messages.css'

withDefaults(
  defineProps<{
    show?: boolean
    className?: string
    class?: any
  }>(),
  {
    show: true,
  },
)
</script>

<template>
  <div :class="['ss-receipt', className, $props.class]" :data-show="show || undefined">
    <span>
      <Roll variant="fade">
        <slot />
      </Roll>
    </span>
  </div>
</template>
