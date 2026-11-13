<script setup lang="ts">
import type { CSSProperties } from 'vue'
import type { CursorKind } from '../cursor'
import './Segmented.css'

export interface SegmentedProps {
  items: any[]
  value: number
  targets?: (string | undefined)[]
  cursor?: CursorKind
  className?: string
  class?: any
  style?: CSSProperties | any
}

defineProps<SegmentedProps>()
</script>

<template>
  <div
    :class="['ss-seg', className, $props.class]"
    :style="{ ['--n' as any]: items.length, ...$props.style }"
    v-bind="$attrs"
  >
    <span class="ss-seg__thumb" :style="{ transform: `translateX(${value * 100}%)` }" />
    <span
      v-for="(o, i) in items"
      :key="i"
      class="ss-seg__option"
      :data-on="i === value || undefined"
      :data-target="targets?.[i]"
      :data-cursor="cursor"
    >
      <component :is="() => o" v-if="typeof o === 'object' && o !== null && 'render' in o" />
      <template v-else>{{ o }}</template>
    </span>
  </div>
</template>
