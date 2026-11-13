<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import type { Rect } from '../measure'
import './Tooltip.css'

export interface TooltipProps {
  show: boolean
  at: Rect
  side?: 'below' | 'above'
  gap?: number
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<TooltipProps>(), {
  side: 'below',
  gap: 6,
})

const x = computed(() => props.at.x + props.at.width / 2)
const y = computed(() =>
  props.side === 'below' ? props.at.y + props.at.height + props.gap : props.at.y - props.gap,
)
</script>

<template>
  <span
    :class="['ss-tooltip', props.className, props.class]"
    :data-show="(props.show && props.at.width > 0) || undefined"
    :data-side="props.side"
    :style="{ left: `${x}px`, top: `${y}px`, ...props.style }"
    role="tooltip"
    v-bind="$attrs"
  >
    <span class="ss-tooltip__label">
      <slot />
    </span>
  </span>
</template>
