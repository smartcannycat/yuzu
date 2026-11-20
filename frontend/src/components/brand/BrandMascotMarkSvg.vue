<script setup lang="ts">
import MascotHeadSvg from '@/components/mascot/MascotHeadSvg.vue'
import { MASCOT_COLORS } from '@/components/mascot/palette'
import YuzuCitrusSvg from '@/components/mascot/YuzuCitrusSvg.vue'

import type { BrandLogoFrame } from './brandMotion'

defineProps<{
  frame: BrandLogoFrame
  size: number
}>()
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="32 14 136 140"
    fill="none"
    :width="size"
    :height="size"
    aria-hidden="true"
    class="pointer-events-none shrink-0 overflow-visible select-none"
  >
    <!-- Chubby loaf body with volume-preserving breathing & boop bounce -->
    <rect
      :x="frame.body.x"
      :y="frame.body.y"
      :width="frame.body.w"
      :height="frame.body.h"
      :rx="frame.body.rx"
      :fill="MASCOT_COLORS.skin"
    />

    <!-- Shared Capybara head + crown Yuzu citrus and boop sparkles -->
    <MascotHeadSvg
      :head-tf="frame.headTf"
      :ear-l="frame.earL"
      :ear-r="frame.earR"
      :open="frame.open"
      :closed-op="frame.closedOp"
      :eyes="frame.eyes"
      :cheek-y="frame.cheekY"
      :cheek-scale="frame.cheekScale"
      :mouth-d="frame.mouthD"
    >
      <template #crown>
        <YuzuCitrusSvg variant="crown" :transform="frame.yuzuTf" :leaf-transform="frame.leafTf" />
        <g
          v-for="(sp, si) in frame.sparks"
          v-show="sp.op > 0.02"
          :key="`sp${si}`"
          :opacity="sp.op"
          :transform="sp.tf"
        >
          <circle cx="0" cy="0" r="3.4" :fill="sp.color" />
        </g>
      </template>
    </MascotHeadSvg>

    <!-- Front paws -->
    <rect x="74" :y="frame.pawY" width="22" height="14" rx="7" :fill="MASCOT_COLORS.muzzle" />
    <rect x="104" :y="frame.pawY" width="22" height="14" rx="7" :fill="MASCOT_COLORS.muzzle" />
  </svg>
</template>
