<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'
import Avatar from './Avatar.vue'
import type { AvatarProps } from './Avatar.vue'
import './Facepile.css'

export interface FacepileProps {
  names: string[]
  size?: number
  overlap?: number
  gap?: number
  tones?: AvatarProps['tone'][]
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<FacepileProps>(), {
  size: 22,
  overlap: 6,
  gap: 2,
})

const r = computed(() => props.size / 2)
const next = computed(() => props.size - props.overlap + r.value)
const mask = computed(
  () =>
    `radial-gradient(circle at ${next.value}px 50%, transparent ${r.value + props.gap}px, #000 ${r.value + props.gap + 0.5}px)`,
)
</script>

<template>
  <span
    :class="['ss-facepile', props.className, props.class]"
    :style="{ ['--ss-overlap' as any]: `${-props.overlap}px`, ...props.style }"
    v-bind="$attrs"
  >
    <span
      v-for="(n, i) in props.names"
      :key="i"
      class="ss-facepile__face"
      :style="i < props.names.length - 1 ? { WebkitMaskImage: mask, maskImage: mask } : undefined"
    >
      <Avatar :name="n" :size="props.size" :tone="props.tones?.[i] ?? 'person'" />
    </span>
  </span>
</template>
