<script setup lang="ts">
import { computed } from 'vue'

import type { BrandLogoLayout, BrandWordmarkStyle } from './BrandLogo.vue'

interface Props {
  layout: BrandLogoLayout
  wordmarkStyle: BrandWordmarkStyle
  subtitle: string
  hideSubtitle: boolean
  responsiveSubtitle: boolean
  letters: string[]
  badgeStyle?: { transform: string }
}

const props = defineProps<Props>()

const wordmarkHeight = computed<number>(() => (props.layout === 'auth' ? 23 : 19))
</script>

<template>
  <div class="pointer-events-none flex min-w-0 flex-col gap-1">
    <div class="flex items-center gap-2">
      <!-- Duolingo-style soft capsule-rounded SVG wordmark for YUZU -->
      <svg
        v-if="wordmarkStyle === 'rounded'"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 109 32"
        fill="none"
        :height="wordmarkHeight"
        class="text-text-primary w-auto shrink-0 overflow-visible"
        role="img"
        aria-label="YUZU"
      >
        <g stroke="currentColor" stroke-width="6.6" stroke-linecap="round" stroke-linejoin="round">
          <path
            :transform="letters[0]"
            d="M 4.5 4.5 L 13.5 16.5 L 22.5 4.5 M 13.5 16.5 L 13.5 27.5"
          />
          <path
            :transform="letters[1]"
            d="M 30.5 4.5 L 30.5 18.5 A 9 9 0 0 0 48.5 18.5 L 48.5 4.5"
          />
          <path :transform="letters[2]" d="M 58.5 4.5 L 76.5 4.5 L 58.5 27.5 L 76.5 27.5" />
          <path
            :transform="letters[3]"
            d="M 86.5 4.5 L 86.5 18.5 A 9 9 0 0 0 104.5 18.5 L 104.5 4.5"
          />
        </g>
      </svg>

      <!-- Fallback Swiss geometric grotesk wordmark -->
      <span
        v-else
        class="text-text-primary leading-none font-bold tracking-[-0.03em]"
        :class="layout === 'auth' ? 'text-[22px]' : 'text-[18px]'"
      >
        YUZU
      </span>

      <span
        v-if="layout === 'report'"
        :style="badgeStyle"
        class="bg-surface-inset text-text-primary border-border inline-flex origin-center items-center rounded-full border px-2 py-0.5 text-[11px] leading-none font-semibold tracking-tight uppercase"
      >
        Report
      </span>

      <span
        v-else
        :style="badgeStyle"
        class="bg-accent-subtle text-accent inline-flex origin-center items-center rounded-full px-2 py-0.5 text-[11px] leading-none font-semibold tracking-tight"
      >
        .auto
      </span>
    </div>

    <span
      v-if="!hideSubtitle"
      class="text-text-secondary inline-flex items-center gap-1.5 leading-snug"
      :class="[
        layout === 'auth' ? 'text-[13px]' : 'text-[12px]',
        layout === 'header' ? 'truncate' : '',
        responsiveSubtitle ? 'hidden sm:inline-flex' : '',
      ]"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 12 12"
        fill="none"
        class="text-accent h-[11px] w-[11px] shrink-0 -translate-y-[0.5px]"
        aria-hidden="true"
      >
        <path
          d="M 4.2 1.5 L 1.8 10.5 M 9.6 1.5 L 7.2 10.5"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        />
      </svg>
      <span class="truncate">{{ subtitle }}</span>
    </span>
  </div>
</template>
