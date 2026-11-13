<script setup lang="ts">
import { computed } from 'vue'

export type BadgeVariant = 'neutral' | 'success' | 'warning' | 'danger' | 'info'
export type BadgeSize = 'sm' | 'md'

interface Props {
  variant?: BadgeVariant
  size?: BadgeSize
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'neutral',
  size: 'md',
})

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: 'bg-surface-inset text-text-secondary',
  success: 'bg-success-bg text-success',
  warning: 'bg-warning-bg text-warning',
  danger: 'bg-danger-bg text-danger',
  info: 'bg-info-bg text-info',
}

const SIZE_CLASSES: Record<BadgeSize, string> = {
  sm: 'min-h-5 px-2 py-0.5 text-[11px] gap-1',
  md: 'min-h-6 px-2.5 py-1 text-[12px] gap-1.5',
}

const variantClasses = computed(() => VARIANT_CLASSES[props.variant])
const sizeClasses = computed(() => SIZE_CLASSES[props.size])
</script>

<template>
  <span
    class="inline-flex items-center rounded-full border-0 leading-none font-medium tracking-[0.01em] whitespace-nowrap [&_svg]:shrink-0 [&_svg]:fill-none [&_svg]:stroke-current"
    :class="[variantClasses, sizeClasses]"
  >
    <slot name="icon" />
    <span>
      <slot />
    </span>
  </span>
</template>
