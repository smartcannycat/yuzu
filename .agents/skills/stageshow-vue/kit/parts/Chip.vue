<script setup lang="ts">
import { ref, onMounted, onUpdated, type CSSProperties } from 'vue'
import Icon from './Icon.vue'
import './Chip.css'

export interface ChipProps {
  show?: boolean
  remove?: string
  gap?: number
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<ChipProps>(), {
  show: true,
  gap: 0,
})

const chip = ref<HTMLSpanElement | null>(null)
const w = ref<number | null>(null)

function measure() {
  if (chip.value) {
    w.value = chip.value.offsetWidth
  }
}

onMounted(() => {
  measure()
})

onUpdated(() => {
  measure()
})
</script>

<template>
  <span
    :class="['ss-chip-slot', props.className, props.class]"
    :data-show="props.show || undefined"
    :style="{
      width: props.show ? (w !== null ? `${w}px` : 'auto') : '0px',
      marginRight: props.show ? '0px' : `${-props.gap}px`,
      ...props.style,
    }"
    v-bind="$attrs"
  >
    <span ref="chip" class="ss-chip" :data-removable="props.remove !== undefined || undefined">
      <span class="ss-chip__label">
        <slot />
      </span>
      <span v-if="props.remove !== undefined" class="ss-chip__x" :data-target="props.remove || undefined">
        <Icon name="close" :size="10" :stroke="1.8" />
      </span>
    </span>
  </span>
</template>
