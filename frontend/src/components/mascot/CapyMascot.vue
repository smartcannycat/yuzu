<script setup lang="ts">
// CapyMascot.vue: YUZU "Zen Inspector" Capybara SVG rig
// Built on viewBox 200 x 170, floor y = 150, head 88 wide centered at (0, 0), neck pivot (0, 30).

import { computed, watch } from 'vue'

import { CAPY_POSES, resolveCapyTiming } from './capyPoses'
import { evaluateCapyFrame } from './capyRigFrame'
import MascotHeadSvg from './MascotHeadSvg.vue'
import MascotPropsSvg from './MascotPropsSvg.vue'
import {
  createChannels,
  resolveCapyState,
  type BatchStatusContract,
  type CapyState,
  type ItemProcessingStatusContract,
  type MascotMoodContract,
  type MascotSize,
  type TrafficLightColorContract,
} from './motion'
import { DEFAULT_CAPY_LABELS, MASCOT_COLORS } from './palette'
import { useMascotClock } from './useMascotClock'

export interface CapyMascotProps {
  /** Direct canonical state override. */
  state?: CapyState
  /** Traffic light verdict from LotDetailResponse / RecalculateResponse. */
  verdict?: TrafficLightColorContract | null
  /** MascotMood from BatchProgressResponse.mascot.mood. */
  mood?: MascotMoodContract | null
  /** Batch status from BatchProgressResponse.status. */
  batchStatus?: BatchStatusContract | null
  /** Single item status from BatchItemStatus.status. */
  itemStatus?: ItemProcessingStatusContract | null
  /** Counts from BatchProgressResponse. */
  readyCount?: number
  failedCount?: number
  /** Local Dropzone state on Screen 2 (files staged or drag-over active). */
  hasSelectedFiles?: boolean
  isDragOver?: boolean
  /** Display mode: 'hero' (208x176 + optional chip) or 'compact' (80x80 avatar). */
  size?: MascotSize
  /** Custom status label for the pill badge below hero mascot. */
  badgeText?: string
  /** Hide the pill badge below the mascot. Defaults to true when size === 'compact'. */
  hideBadge?: boolean
  /** Enable calm idle and state-transition motion. Defaults to true. */
  animated?: boolean
}

const props = withDefaults(defineProps<CapyMascotProps>(), {
  state: undefined,
  verdict: null,
  mood: null,
  batchStatus: null,
  itemStatus: null,
  readyCount: undefined,
  failedCount: undefined,
  hasSelectedFiles: false,
  isDragOver: false,
  size: 'hero',
  badgeText: undefined,
  hideBadge: undefined,
  animated: true,
})

const activeState = computed<CapyState>(() =>
  resolveCapyState({
    state: props.state,
    verdict: props.verdict,
    mood: props.mood,
    batchStatus: props.batchStatus,
    itemStatus: props.itemStatus,
    readyCount: props.readyCount,
    failedCount: props.failedCount,
    hasSelectedFiles: props.hasSelectedFiles,
    isDragOver: props.isDragOver,
  }),
)

const isCompact = computed(() => props.size === 'compact')
const shouldHideBadge = computed(() => props.hideBadge ?? isCompact.value)
const statusLabel = computed(() => props.badgeText || DEFAULT_CAPY_LABELS[activeState.value])

const ch = createChannels(CAPY_POSES[activeState.value])
const { root, now, t0, isActive, start } = useMascotClock({
  animated: () => props.animated,
})

watch(activeState, (nextState) => {
  const T = performance.now()
  ch.retarget(CAPY_POSES[nextState], T, resolveCapyTiming, !isActive.value)
  if (!isActive.value) now.value = T
  else start()
})

const p = computed(() =>
  evaluateCapyFrame(ch, now.value, t0.value, isActive.value, isCompact.value),
)
</script>

<template>
  <div
    ref="root"
    class="mascot-container flex flex-col items-center justify-center select-none"
    :class="isCompact ? 'h-full w-full' : 'w-full'"
  >
    <!-- SVG Mascot Stage -->
    <div
      :class="
        isCompact
          ? 'relative flex h-full w-full items-center justify-center'
          : 'relative flex h-44 w-52 items-center justify-center'
      "
    >
      <svg
        :viewBox="isCompact ? '8 4 186 156' : '0 0 200 170'"
        class="h-full w-full overflow-visible"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        :aria-label="statusLabel"
      >
        <!-- Floor shadow: flat pill (Duolingo flat perspective rule) -->
        <rect
          :x="100 - p.shadowW / 2"
          y="144"
          :width="p.shadowW"
          height="12"
          rx="6"
          :fill="MASCOT_COLORS.shadow"
        />

        <!-- Body: sleeping loaf <-> sitting capsule -->
        <rect
          :x="p.body.x"
          :y="p.body.y"
          :width="p.body.w"
          :height="p.body.h"
          :rx="p.body.rx"
          :fill="MASCOT_COLORS.skin"
        />

        <!-- Head group (neck pivot at (0, 30)) -->
        <MascotHeadSvg
          :head-tf="p.headTf"
          :ear-l="p.earL"
          :ear-r="p.earR"
          :open="p.open"
          :closed-op="p.closedOp"
          :eyes="p.eyes"
          :cheek-y="p.cheekY"
          :mouth-d="p.mouth"
        />

        <!-- State props, paws, and floating glyphs -->
        <MascotPropsSvg :pose="p" />
      </svg>
    </div>

    <!-- Clean Light Seamless Status Pill (Hero mode) -->
    <div
      v-if="!shouldHideBadge"
      class="mt-1.5 inline-flex items-center gap-2 rounded-full px-3 py-1 text-[12px] font-medium transition-colors duration-200"
      :class="{
        'bg-success-bg text-success': activeState === 'green',
        'bg-warning-bg text-warning': activeState === 'yellow',
        'bg-danger-bg text-danger': activeState === 'red' || activeState === 'error',
        'bg-accent-subtle text-accent': activeState === 'thinking' || activeState === 'peeking',
        'bg-surface-inset text-text-secondary': activeState === 'sleeping',
      }"
    >
      <span
        class="h-2 w-2 rounded-full transition-colors duration-200"
        :class="{
          'bg-success': activeState === 'green',
          'bg-warning': activeState === 'yellow',
          'bg-danger': activeState === 'red' || activeState === 'error',
          'bg-accent animate-pulse': activeState === 'thinking',
          'bg-accent': activeState === 'peeking',
          'bg-text-muted': activeState === 'sleeping',
        }"
      />
      <Transition name="yuzu-chip" mode="out-in">
        <span :key="`${activeState}-${statusLabel}`">{{ statusLabel }}</span>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.yuzu-chip-enter-active {
  transition:
    opacity 180ms cubic-bezier(0.23, 1, 0.32, 1),
    transform 180ms cubic-bezier(0.23, 1, 0.32, 1);
}
.yuzu-chip-leave-active {
  transition:
    opacity 120ms ease-in,
    transform 120ms ease-in;
}
.yuzu-chip-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
.yuzu-chip-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .yuzu-chip-enter-active,
  .yuzu-chip-leave-active {
    transition: none;
  }
}
</style>
