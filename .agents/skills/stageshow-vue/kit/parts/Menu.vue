<script setup lang="ts">
import type { CSSProperties } from 'vue'
import './Menu.css'

defineProps<{
  items: any[]
  value?: number
  targets?: (string | undefined)[]
  className?: string
  class?: any
  style?: CSSProperties | any
}>()
</script>

<template>
  <div :class="['ss-menu', className, $props.class]" :style="$props.style" role="menu" v-bind="$attrs">
    <div
      v-for="(item, i) in items"
      :key="i"
      class="ss-menu__item"
      :data-active="i === value || undefined"
      :data-target="targets?.[i]"
      role="menuitem"
    >
      <component :is="() => item" v-if="typeof item === 'object' && item !== null && 'render' in item" />
      <template v-else>{{ item }}</template>
    </div>
  </div>
</template>
