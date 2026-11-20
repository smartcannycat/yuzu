<script setup lang="ts">
import { computed, ref } from 'vue'

import { useMascotClock } from '@/components/mascot/useMascotClock'

import BrandMascotMarkSvg from './BrandMascotMarkSvg.vue'
import { evaluateBrandLogoFrame } from './brandMotion'
import BrandWordmark from './BrandWordmark.vue'

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
  /** Enable calm idle motion and click/tap boop interaction on the Capybara mark. Defaults to true. */
  animated?: boolean
}

const props = withDefaults(defineProps<BrandLogoProps>(), {
  layout: 'header',
  variant: 'mascot',
  wordmarkStyle: 'rounded',
  size: undefined,
  subtitle: undefined,
  hideSubtitle: false,
  responsiveSubtitle: false,
  animated: true,
})

const emit = defineEmits<{
  boop: [count: number]
}>()

const resolvedSize = computed<number>(() => {
  if (typeof props.size === 'number' && props.size > 0) return props.size
  if (props.layout === 'auth') return 54
  if (props.layout === 'report') return 44
  return 42
})

const resolvedSubtitle = computed<string>(() => {
  if (props.subtitle !== undefined) return props.subtitle
  if (props.layout === 'report') {
    return 'Экспертная дефектоскопия и расчет под ключ'
  }
  return 'Интеллект японских автоаукционов'
})

const hovered = ref(false)
const boopCount = ref(0)
const boopStart = ref(-99999)
const hoverChangedAt = ref(performance.now() - 220)

const { root, now, t0, reduced, isActive, start } = useMascotClock({
  animated: () => props.animated,
})

function triggerBoop(): void {
  if (!props.animated) return
  const ts = performance.now()
  boopStart.value = ts
  boopCount.value += 1
  now.value = ts
  emit('boop', boopCount.value)
  if (!reduced.value) {
    start()
  }
}

function onPointerEnter(): void {
  hovered.value = true
  hoverChangedAt.value = performance.now()
  start()
}

function onPointerLeave(): void {
  hovered.value = false
  hoverChangedAt.value = performance.now()
}

const anim = computed(() =>
  evaluateBrandLogoFrame({
    T: now.value,
    t0: t0.value,
    active: isActive.value,
    hovered: hovered.value,
    hoverChangedAt: hoverChangedAt.value,
    boopStart: boopStart.value,
    boopCount: boopCount.value,
  }),
)
</script>

<template>
  <div
    ref="root"
    :role="animated ? 'button' : undefined"
    :tabindex="animated ? 0 : undefined"
    :aria-label="animated ? 'YUZU — нажмите для анимации логотипа' : undefined"
    class="focus-visible:outline-accent inline-flex min-w-0 items-center rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4"
    :class="[
      layout === 'auth' ? 'gap-3.5' : 'gap-2.5',
      animated ? 'cursor-pointer select-none' : '',
    ]"
    @click="triggerBoop"
    @keydown.enter.prevent="triggerBoop"
    @keydown.space.prevent="triggerBoop"
    @pointerenter="onPointerEnter"
    @pointerleave="onPointerLeave"
  >
    <BrandMascotMarkSvg v-if="variant === 'mascot'" :frame="anim" :size="resolvedSize" />

    <BrandWordmark
      v-if="layout !== 'mark'"
      :layout="layout"
      :wordmark-style="wordmarkStyle"
      :subtitle="resolvedSubtitle"
      :hide-subtitle="hideSubtitle"
      :responsive-subtitle="responsiveSubtitle"
      :letters="anim.letters"
      :badge-style="anim.badgeStyle"
    />
  </div>
</template>
