<script setup lang="ts">
import { computed } from 'vue'

export type BrandLogoLayout = 'header' | 'auth' | 'report' | 'mark'
export type BrandLogoVariant = 'mascot' | 'wordmark'
export type BrandWordmarkStyle = 'rounded' | 'swiss'

export interface BrandLogoProps {
  layout?: BrandLogoLayout
  /** 'mascot' renders the unified Capybara Yuzu mark + wordmark; 'wordmark' renders text lockup only. */
  variant?: BrandLogoVariant
  /** 'rounded' renders custom Duolingo-style capsule-stroke SVG letters for YUZU; 'swiss' uses geometric grotesk. */
  wordmarkStyle?: BrandWordmarkStyle
  size?: number
  subtitle?: string
  hideSubtitle?: boolean
  responsiveSubtitle?: boolean
}

const props = withDefaults(defineProps<BrandLogoProps>(), {
  layout: 'header',
  variant: 'mascot',
  wordmarkStyle: 'rounded',
  size: undefined,
  subtitle: undefined,
  hideSubtitle: false,
  responsiveSubtitle: false,
})

const uid = `yuzu-brand-${Math.random().toString(36).slice(2, 8)}`

const resolvedSize = computed<number>(() => {
  if (typeof props.size === 'number' && props.size > 0) return props.size
  if (props.layout === 'auth') return 54
  if (props.layout === 'report') return 44
  return 42
})

const wordmarkHeight = computed<number>(() => (props.layout === 'auth' ? 23 : 19))

const resolvedSubtitle = computed<string>(() => {
  if (props.subtitle !== undefined) return props.subtitle
  if (props.layout === 'report') {
    return 'Экспертная дефектоскопия и расчет под ключ'
  }
  return 'Интеллект японских автоаукционов'
})

// Exact palette and geometry from CapyMascot.vue
const C = {
  skin: '#A56644',
  skinShade: '#8C5235',
  feature: '#5C3520',
  muzzle: '#E5A259',
  pupil: '#3C3C3C',
  white: '#FFFFFF',
  cheek: '#FFB2B2',
  yuzu: '#FFC800',
  yuzuShade: '#FFB100',
  leaf: '#58CC02',
}

const EYES = [-20, 20] as const
const EYE_Y = -14
</script>

<template>
  <div class="inline-flex min-w-0 items-center" :class="layout === 'auth' ? 'gap-3.5' : 'gap-2.5'">
    <!-- Unified Capybara Yuzu Mark (1:1 proportions from CapyMascot.vue, no border stroke or floor shadow) -->
    <svg
      v-if="variant === 'mascot'"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="32 14 136 140"
      fill="none"
      :width="resolvedSize"
      :height="resolvedSize"
      class="shrink-0 overflow-visible select-none"
      aria-hidden="true"
    >
      <defs>
        <clipPath v-for="(cx, i) in EYES" :id="`${uid}-eye${i}`" :key="`e${i}`">
          <rect :x="cx - 10" :y="EYE_Y - 13" width="20" height="26" rx="10" />
        </clipPath>
        <clipPath v-for="(cx, i) in EYES" :id="`${uid}-lid${i}`" :key="`l${i}`">
          <rect :x="cx - 12" :y="EYE_Y - 15" width="24" height="30" rx="12" />
        </clipPath>
      </defs>

      <!-- Chubby loaf body (exact W=123, H=57.25, rx=26.3 at y=92.75..150 from CapyMascot peeking pose) -->
      <rect x="38.5" y="92.75" width="123" height="57.25" rx="26.3" :fill="C.skin" />

      <!-- Head group centered at (100, 87) -->
      <g transform="translate(100 87)">
        <!-- Ears -->
        <rect
          x="-38"
          y="-45"
          width="15"
          height="18"
          rx="7.5"
          :fill="C.skinShade"
          transform="rotate(-2 -30 -30)"
        />
        <rect
          x="23"
          y="-45"
          width="15"
          height="18"
          rx="7.5"
          :fill="C.skinShade"
          transform="rotate(2 30 -30)"
        />

        <!-- Head: rounded tombstone block (88 x 76, rx=34) -->
        <rect x="-44" y="-38" width="88" height="76" rx="34" :fill="C.skin" />

        <!-- Signature Yuzu citrus seated on crown of head (same geometry as CapyMascot finial) -->
        <g transform="translate(0 -46)">
          <rect
            x="1.5"
            y="-18"
            width="13"
            height="6.4"
            rx="3.2"
            :fill="C.leaf"
            transform="rotate(-22 1.5 -15)"
          />
          <circle cx="0" cy="-2" r="11.5" :fill="C.yuzu" />
          <path
            d="M 11.5 -2 A 11.5 11.5 0 0 1 -4.3 8.6 A 14.4 14.4 0 0 1 11.5 -2 Z"
            :fill="C.yuzuShade"
          />
          <rect x="-6.5" y="-8.5" width="4" height="6.4" rx="2" :fill="C.white" />
        </g>

        <!-- Muzzle (64 x 36, rx=17) -->
        <rect x="-32" y="0" width="64" height="36" rx="17" :fill="C.muzzle" />

        <!-- Cheeks -->
        <rect x="-42" y="6" width="11" height="7" rx="3.5" :fill="C.cheek" />
        <rect x="31" y="6" width="11" height="7" rx="3.5" :fill="C.cheek" />

        <!-- Nostrils + smile -->
        <rect x="-9" y="8" width="6" height="8" rx="3" :fill="C.feature" />
        <rect x="3" y="8" width="6" height="8" rx="3" :fill="C.feature" />
        <path
          d="M -6.2 23 Q 0 27.2 6.2 23 Q 0 27.2 -6.2 23 Z"
          :fill="C.feature"
          :stroke="C.feature"
          stroke-width="3"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- Awake eyes (20 x 26 white pills, 10 x 15 pupils, skin lids) -->
        <g v-for="(cx, i) in EYES" :key="`eye${i}`">
          <rect :x="cx - 10" :y="EYE_Y - 13" width="20" height="26" rx="10" :fill="C.white" />
          <g :clip-path="`url(#${uid}-eye${i})`">
            <rect :x="cx - 5" :y="EYE_Y - 8.5" width="10" height="15" rx="5" :fill="C.pupil" />
            <circle :cx="cx - 1.5" :cy="EYE_Y - 4.5" r="2.2" :fill="C.white" />
          </g>
          <g :clip-path="`url(#${uid}-lid${i})`">
            <rect :x="cx - 14" :y="EYE_Y - 17" width="28" height="4.2" :fill="C.skin" />
            <rect :x="cx - 12" :y="EYE_Y + 11.5" width="24" height="3.5" :fill="C.skin" />
          </g>
        </g>
      </g>

      <!-- Front paws (pawLX=85, pawRX=115, pawY=143, 22x14, rx=7) -->
      <rect x="74" y="136" width="22" height="14" rx="7" :fill="C.muzzle" />
      <rect x="104" y="136" width="22" height="14" rx="7" :fill="C.muzzle" />
    </svg>

    <!-- Unified Wordmark & Institutional Descriptor Lockup -->
    <div v-if="layout !== 'mark'" class="flex min-w-0 flex-col gap-1">
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
          <g
            stroke="currentColor"
            stroke-width="6.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- Y -->
            <path d="M 4.5 4.5 L 13.5 16.5 L 22.5 4.5 M 13.5 16.5 L 13.5 27.5" />
            <!-- U -->
            <path d="M 30.5 4.5 L 30.5 18.5 A 9 9 0 0 0 48.5 18.5 L 48.5 4.5" />
            <!-- Z -->
            <path d="M 58.5 4.5 L 76.5 4.5 L 58.5 27.5 L 76.5 27.5" />
            <!-- U -->
            <path d="M 86.5 4.5 L 86.5 18.5 A 9 9 0 0 0 104.5 18.5 L 104.5 4.5" />
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
          class="bg-surface-inset text-text-primary border-border inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] leading-none font-semibold tracking-tight uppercase"
        >
          Report
        </span>

        <span
          v-else
          class="bg-accent-subtle text-accent inline-flex items-center rounded-full px-2 py-0.5 text-[11px] leading-none font-semibold tracking-tight"
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
        <span class="truncate">{{ resolvedSubtitle }}</span>
      </span>
    </div>
  </div>
</template>
