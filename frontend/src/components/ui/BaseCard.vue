<script setup lang="ts">
import { computed } from 'vue'

export type CardVariant =
  | 'surface'
  | 'inset'
  | 'verdict-safe'
  | 'verdict-warning'
  | 'verdict-danger'
export type CardPadding = 'none' | 'sm' | 'md' | 'lg'

interface Props {
  variant?: CardVariant
  padding?: CardPadding
  as?: 'div' | 'section' | 'article'
  interactive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'surface',
  padding: 'md',
  as: 'div',
  interactive: false,
})

const VARIANT_CLASSES: Record<CardVariant, string> = {
  surface: 'bg-surface border border-border shadow-card',
  inset: 'bg-surface-inset border border-transparent',
  'verdict-safe':
    'border border-success/25 bg-gradient-to-b from-surface to-success-bg shadow-card',
  'verdict-warning':
    'border border-warning/25 bg-gradient-to-b from-surface to-warning-bg shadow-card',
  'verdict-danger':
    'border border-danger/25 bg-gradient-to-b from-surface to-danger-bg shadow-card',
}

const PADDING_CLASSES: Record<CardPadding, string> = {
  none: 'p-0',
  sm: 'p-3',
  md: 'p-4 sm:p-5',
  lg: 'p-5 sm:p-7',
}

const variantClasses = computed(() => VARIANT_CLASSES[props.variant])
const paddingClasses = computed(() => PADDING_CLASSES[props.padding])
</script>

<template>
  <component
    :is="as"
    class="text-text-primary rounded-md transition-[border-color,background-color] duration-150"
    :class="[
      variantClasses,
      paddingClasses,
      interactive ? 'hover:border-border-strong active:bg-surface-hover cursor-pointer' : '',
    ]"
  >
    <slot />
  </component>
</template>
