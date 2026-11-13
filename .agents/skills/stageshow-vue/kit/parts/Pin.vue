<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import { useLook } from '../looks'
import './Pin.css'

export interface PinProps {
  name?: string
  src?: string
  size?: number
  corner?: 'bl' | 'br' | 'tl' | 'tr'
  tone?: 'accent' | 'ink'
  selected?: boolean
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<PinProps>(), {
  name: '',
  size: 24,
  corner: 'bl',
  tone: 'accent',
})

const look = useLook()
const plain = computed(() => look.fidelity === 'minimal')

const pinStyle = computed<CSSProperties>(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.round(props.size * 0.42)}px`,
  ...props.style,
}))
</script>

<template>
  <span
    :class="['ss-pin', props.className, props.class]"
    :data-corner="props.corner"
    :data-tone="props.tone"
    :data-selected="props.selected || undefined"
    :style="pinStyle"
    v-bind="$attrs"
  >
    <span class="ss-pin__face">
      <img v-if="props.src && !plain" :src="props.src" alt="" />
      <template v-else-if="!plain">{{ props.name.trim()[0]?.toUpperCase() }}</template>
    </span>
  </span>
</template>
