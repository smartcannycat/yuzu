<script setup lang="ts">
import './Badge.css'

export interface BadgeProps {
  tone?: 'neutral' | 'accent' | 'success' | 'danger' | 'warning'
  dot?: boolean
  icon?: any
  className?: string
  class?: any
}

const props = withDefaults(defineProps<BadgeProps>(), {
  tone: 'neutral',
})
</script>

<template>
  <span
    :class="['ss-badge', props.className, props.class]"
    :data-tone="props.tone"
    :data-lead="props.dot || props.icon || $slots.icon ? '' : undefined"
  >
    <span v-if="props.dot" class="ss-badge__dot" />
    <slot name="icon">
      <component :is="() => props.icon" v-if="props.icon" />
    </slot>
    <span class="ss-badge__label">
      <slot />
    </span>
  </span>
</template>
