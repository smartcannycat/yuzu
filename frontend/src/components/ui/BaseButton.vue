<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'
import { computed } from 'vue'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface Props {
  variant?: ButtonVariant
  size?: ButtonSize
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  loading?: boolean
  block?: boolean
  pill?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  type: 'button',
  disabled: false,
  loading: false,
  block: false,
  pill: false,
})

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-text-on-accent border border-accent hover:bg-accent-hover active:bg-accent-active',
  secondary:
    'bg-surface-inset text-text-primary border border-transparent hover:bg-border active:bg-border-strong/60',
  ghost:
    'bg-transparent text-text-primary border border-border hover:bg-surface-hover hover:border-text-secondary active:bg-surface-inset',
  destructive:
    'bg-danger-bg text-danger border border-transparent hover:bg-danger/15 active:bg-danger/20',
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-[13px] rounded-sm gap-1.5',
  md: 'h-10 px-4 text-[14px] rounded-sm gap-2',
  lg: 'h-12 px-[22px] text-[16px] rounded-md gap-2',
}

const ICON_SIZES: Record<ButtonSize, number> = {
  sm: 14,
  md: 16,
  lg: 18,
}

const isDisabled = computed(() => props.disabled || props.loading)

const variantClasses = computed(() => {
  if (props.disabled && !props.loading) {
    return 'bg-canvas text-text-muted border border-border cursor-not-allowed'
  }
  return VARIANT_CLASSES[props.variant]
})

const sizeClasses = computed(() => SIZE_CLASSES[props.size])
const iconSize = computed(() => ICON_SIZES[props.size])
</script>

<template>
  <button
    :type="type"
    :disabled="isDisabled"
    :aria-busy="loading || undefined"
    class="focus-visible:outline-accent inline-flex items-center justify-center font-medium whitespace-nowrap transition-[background-color,border-color,color,scale,opacity] duration-[var(--duration-quick)] ease-[var(--ease-out)] select-none focus-visible:outline-2 focus-visible:outline-offset-2"
    :class="[
      variantClasses,
      sizeClasses,
      pill ? 'rounded-full!' : '',
      block ? 'w-full' : '',
      isDisabled
        ? loading
          ? 'cursor-wait opacity-90'
          : 'cursor-not-allowed'
        : 'cursor-pointer active:scale-[0.98]',
    ]"
  >
    <LoaderCircle
      v-if="loading"
      :size="iconSize"
      :stroke-width="2"
      class="shrink-0 animate-spin"
      aria-hidden="true"
    />
    <slot v-else name="icon-left" />
    <span class="inline-flex items-center gap-1.5">
      <slot />
    </span>
    <slot name="icon-right" />
  </button>
</template>
