<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import { computed, useSlots } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'

import { sanitizeNavigationHref } from '@/utils/url'

interface Props {
  title: string
  subtitle?: string
  value?: string
  squircleColor?: string
  chevron?: boolean
  interactive?: boolean
  disabled?: boolean
  to?: RouteLocationRaw
  href?: string
}

const props = withDefaults(defineProps<Props>(), {
  chevron: false,
  interactive: false,
  disabled: false,
})

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const slots = useSlots()
const hasIcon = computed(() => Boolean(slots.icon))
const safeHref = computed(() => sanitizeNavigationHref(props.href))
const isInteractive = computed(
  () => !props.disabled && (props.interactive || Boolean(props.to) || Boolean(safeHref.value)),
)

const tagName = computed(() => {
  if (props.to && !props.disabled) return RouterLink
  if (safeHref.value && !props.disabled) return 'a'
  if (props.interactive) return 'button'
  return 'div'
})

const linkAttrs = computed(() => {
  if (props.to && !props.disabled) return { to: props.to }
  if (safeHref.value && !props.disabled) {
    const isExternal = /^https?:\/\//i.test(safeHref.value)
    return isExternal
      ? { href: safeHref.value, target: '_blank', rel: 'noopener noreferrer' }
      : { href: safeHref.value }
  }
  if (props.interactive) return { type: 'button' as const, disabled: props.disabled }
  return {}
})

function handleClick(event: MouseEvent) {
  if (props.disabled) return
  if (isInteractive.value) {
    emit('click', event)
  }
}
</script>

<template>
  <component
    :is="tagName"
    v-bind="linkAttrs"
    class="focus-visible:outline-accent not-last:after:bg-border relative flex min-h-12 w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors duration-[var(--duration-quick)] ease-[var(--ease-out)] not-last:after:absolute not-last:after:right-0 not-last:after:bottom-0 not-last:after:h-px not-last:after:content-[''] focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
    :class="[
      hasIcon ? 'not-last:after:left-14' : 'not-last:after:left-4',
      isInteractive ? 'hover:bg-surface-hover active:bg-surface-inset/70 cursor-pointer' : '',
      disabled ? 'cursor-not-allowed opacity-55' : '',
    ]"
    @click="handleClick"
  >
    <div class="flex min-w-0 flex-1 items-center gap-3">
      <div
        v-if="hasIcon"
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] text-white [&_svg]:stroke-current"
        :style="{ backgroundColor: squircleColor ?? '#FF6B00' }"
        aria-hidden="true"
      >
        <slot name="icon" />
      </div>

      <div class="flex min-w-0 flex-col gap-0.5">
        <span class="text-text-primary text-[15px] leading-snug font-normal wrap-break-word">
          {{ title }}
        </span>
        <span v-if="subtitle" class="text-text-secondary text-[12px] leading-snug wrap-break-word">
          {{ subtitle }}
        </span>
      </div>
    </div>

    <div class="text-text-secondary flex shrink-0 items-center gap-1.5 text-[14px]">
      <slot name="trailing">
        <span v-if="value" class="text-right tabular-nums">{{ value }}</span>
      </slot>
      <ChevronRight
        v-if="chevron"
        :size="16"
        :stroke-width="2"
        class="text-text-muted"
        aria-hidden="true"
      />
    </div>
  </component>
</template>
