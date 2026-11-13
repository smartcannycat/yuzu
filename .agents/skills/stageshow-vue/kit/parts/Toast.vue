<script setup lang="ts">
import { computed, useSlots, type CSSProperties } from 'vue'
import { useLook } from '../looks'
import './Toast.css'

export interface ToastProps {
  show: boolean
  icon?: any
  action?: any
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = defineProps<ToastProps>()
const slots = useSlots()
const look = useLook()

const textContent = computed(() => {
  const d = slots.default?.()
  if (!d || !d.length) return ''
  const first = d[0]
  if (typeof first.children === 'string') return first.children
  return String(first.children ?? '')
})

const isMinimal = computed(() => look.fidelity === 'minimal')
const minimalWidth = computed(() => Math.min(160, textContent.value.length * 5.5))
</script>

<template>
  <div
    :class="['ss-toast', props.className, props.class]"
    :data-show="props.show || undefined"
    :style="props.style"
    role="status"
    v-bind="$attrs"
  >
    <span v-if="props.icon || $slots.icon" class="ss-toast__icon">
      <slot name="icon">
        <component :is="() => props.icon" v-if="typeof props.icon === 'object' && props.icon !== null && 'render' in props.icon" />
        <template v-else>{{ props.icon }}</template>
      </slot>
    </span>

    <span>
      <span
        v-if="isMinimal"
        class="ss-bar"
        :style="{ width: `${minimalWidth}px`, height: '6px', borderRadius: '3px', background: 'var(--ss-ink-3)', display: 'inline-block' }"
      />
      <slot v-else />
    </span>

    <span v-if="props.action || $slots.action" class="ss-toast__action">
      <slot name="action">
        <component :is="() => props.action" v-if="typeof props.action === 'object' && props.action !== null && 'render' in props.action" />
        <template v-else>{{ props.action }}</template>
      </slot>
    </span>
  </div>
</template>
