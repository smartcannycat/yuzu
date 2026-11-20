<script setup lang="ts">
import { computed } from 'vue'

import { MASCOT_COLORS } from './palette'

interface Props {
  variant?: 'crown' | 'finial'
  transform?: string
  leafTransform?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'crown',
  transform: undefined,
  leafTransform: undefined,
})

const spec = computed(() =>
  props.variant === 'finial'
    ? {
        leafX: 1,
        leafY: -13,
        leafW: 9,
        leafH: 4.5,
        leafRx: 2.25,
        defaultLeafTf: 'rotate(-22 1 -11)',
        radius: 8,
        shadePath: 'M 8 -2 A 8 8 0 0 1 -3 5.4 A 10 10 0 0 1 8 -2 Z',
        hlX: -4.5,
        hlY: -6.5,
        hlW: 2.8,
        hlH: 4.5,
        hlRx: 1.4,
      }
    : {
        leafX: 1.5,
        leafY: -18,
        leafW: 13,
        leafH: 6.4,
        leafRx: 3.2,
        defaultLeafTf: 'rotate(-22 1.5 -15)',
        radius: 11.5,
        shadePath: 'M 11.5 -2 A 11.5 11.5 0 0 1 -4.3 8.6 A 14.4 14.4 0 0 1 11.5 -2 Z',
        hlX: -6.5,
        hlY: -8.5,
        hlW: 4,
        hlH: 6.4,
        hlRx: 2,
      },
)
</script>

<template>
  <g :transform="transform">
    <rect
      :x="spec.leafX"
      :y="spec.leafY"
      :width="spec.leafW"
      :height="spec.leafH"
      :rx="spec.leafRx"
      :fill="MASCOT_COLORS.leaf"
      :transform="leafTransform ?? spec.defaultLeafTf"
    />
    <circle cx="0" cy="-2" :r="spec.radius" :fill="MASCOT_COLORS.yuzu" />
    <path :d="spec.shadePath" :fill="MASCOT_COLORS.yuzuShade" />
    <rect
      :x="spec.hlX"
      :y="spec.hlY"
      :width="spec.hlW"
      :height="spec.hlH"
      :rx="spec.hlRx"
      :fill="MASCOT_COLORS.white"
    />
  </g>
</template>
