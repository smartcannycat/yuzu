<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  EASE_IN_OUT,
  bell,
  clamp01,
  loop,
  mix,
  track,
  wave,
  type KeyFrame,
} from '@/components/mascot/motion'

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
  sparkOrange: '#FF6B00',
}

const EYES = [-20, 20] as const
const EYE_Y = -14

// Idle keyframe tracks (blink, ear twitch, subtle glance toward wordmark)
const BLINK: KeyFrame[] = [
  [0, 1],
  [2800, 1],
  [2900, 0],
  [2950, 0],
  [3120, 1, 'out'],
  [4200, 1],
]

const EAR_TWITCH: KeyFrame[] = [
  [0, 0],
  [4100, 0],
  [4210, -13],
  [4330, 0],
  [4440, -8, 'out'],
  [4600, 0],
  [5800, 0],
]

const GLANCE_X: KeyFrame[] = [
  [0, 0],
  [2400, 0],
  [2750, 2.2, 'out'],
  [3900, 2.2],
  [4300, 0, 'io'],
  [7200, 0],
]

// Hop trajectory during a click/tap boop (0..1150 ms):
// 0..140 ms: cozy anticipation squash (+2.8px down)
// 140..420 ms: cheerful hop up (-7.5px)
// 420..700 ms: soft landing settle (+1.2px)
// 700..1150 ms: return to rest (0)
const BOOP_HEAD_Y: KeyFrame[] = [
  [0, 0],
  [120, 2.8, 'io'],
  [340, -7.2, 'out'],
  [580, 1.2, 'in'],
  [820, -0.8, 'out'],
  [1150, 0, 'io'],
]

// Yuzu citrus on head has follow-through lag: launches higher as head peaks, lands with a tiny bounce
const BOOP_YUZU_Y: KeyFrame[] = [
  [0, 0],
  [140, 1.5, 'io'],
  [390, -13.5, 'out'],
  [640, 1.6, 'in'],
  [840, -2.4, 'out'],
  [1150, 0, 'io'],
]

const BOOP_DURATION = 1150

const root = ref<HTMLElement | null>(null)
const now = ref(performance.now())
const reduced = ref(false)
const hovered = ref(false)
const boopCount = ref(0)
let t0 = performance.now()
let boopStart = -99999
let hoverChangedAt = performance.now()
let raf = 0
let onScreen = true
let mql: MediaQueryList | null = null
let io: IntersectionObserver | null = null

function frame(ts: number) {
  now.value = ts
  raf = requestAnimationFrame(frame)
}

function start() {
  if (!props.animated || raf || reduced.value || !onScreen || document.hidden) return
  raf = requestAnimationFrame(frame)
}

function stop() {
  if (raf) cancelAnimationFrame(raf)
  raf = 0
}

function onVisibility() {
  if (document.hidden) stop()
  else start()
}

function onReducedChange() {
  reduced.value = !!mql?.matches
  if (reduced.value) {
    stop()
    now.value = performance.now()
  } else {
    start()
  }
}

function triggerBoop() {
  if (!props.animated) return
  const ts = performance.now()
  boopStart = ts
  boopCount.value += 1
  now.value = ts
  emit('boop', boopCount.value)
  if (!reduced.value) {
    start()
  }
}

function onPointerEnter() {
  hovered.value = true
  hoverChangedAt = performance.now()
  start()
}

function onPointerLeave() {
  hovered.value = false
  hoverChangedAt = performance.now()
}

onMounted(() => {
  t0 = performance.now()
  mql = window.matchMedia?.('(prefers-reduced-motion: reduce)') ?? null
  reduced.value = !!mql?.matches
  mql?.addEventListener?.('change', onReducedChange)
  document.addEventListener('visibilitychange', onVisibility)
  if ('IntersectionObserver' in window && root.value) {
    io = new IntersectionObserver(([entry]) => {
      onScreen = !!entry?.isIntersecting
      if (onScreen) start()
      else stop()
    })
    io.observe(root.value)
  }
  start()
})

onBeforeUnmount(() => {
  stop()
  io?.disconnect()
  mql?.removeEventListener?.('change', onReducedChange)
  document.removeEventListener('visibilitychange', onVisibility)
})

const anim = computed(() => {
  const T = now.value
  const active = props.animated && !reduced.value
  const t = active ? T - t0 : 0

  // Smooth hover factor (0..1 over 220 ms)
  const hoverElapsed = clamp01((T - hoverChangedAt) / 220)
  const hoverW = active ? (hovered.value ? hoverElapsed : 1 - hoverElapsed) : 0

  // Boop progress (0..1 over BOOP_DURATION ms)
  const boopElapsed = T - boopStart
  const isBooping = active && boopElapsed >= 0 && boopElapsed < BOOP_DURATION
  const boopQ = isBooping ? clamp01(boopElapsed / BOOP_DURATION) : 0
  const boopEnv = isBooping ? bell(boopQ) : 0

  // Calm breathing loaf (4200 ms period) + boop squash/stretch
  const b = active ? wave(t, 4200) : 0
  const bLate = active ? wave(t - 140, 4200) : 0
  const boopHeadDy = isBooping ? track(boopElapsed, BOOP_HEAD_Y) : 0
  const boopSquash = isBooping ? clamp01(1 - Math.abs(boopElapsed - 110) / 110) * 0.08 : 0
  const boopStretch = isBooping ? clamp01(1 - Math.abs(boopElapsed - 340) / 180) * 0.06 : 0

  const sy = 1 + 0.022 * b - boopSquash + boopStretch
  const sx = 1 / Math.pow(sy, 0.6)
  const bodyW = 123 * sx
  const bodyH = 57.25 * sy

  // Head position and tilt
  const headY = 87 - 1.2 * bLate - 1.2 * hoverW + boopHeadDy
  const headTilt =
    (active ? 1.3 * wave(t, 3800, 0.15) : 0) +
    hoverW * -2.2 +
    (isBooping ? 5.5 * Math.sin(boopQ * Math.PI * 2) * (1 - boopQ * 0.5) : 0)

  // Ears: gentle wave + periodic twitch + hover perk + boop flap
  const twitch = active ? track(loop(t, 5800) * 5800, EAR_TWITCH) : 0
  const boopEar = isBooping ? -12 * Math.sin(boopQ * Math.PI * 2) * (1 - boopQ) : 0
  const earL = -2 - (active ? 1.8 * wave(t, 3100) : 0) - 4 * hoverW + boopEar
  const earR = 2 + (active ? 1.8 * wave(t, 2700, 0.35) : 0) + twitch + 4 * hoverW - boopEar

  // Eyes: open with periodic blink, switching to happy ^ ^ arches during a boop
  const blink = active ? track(loop(t, 4200) * 4200, BLINK) : 1
  const happy = isBooping ? clamp01(Math.sin(boopQ * Math.PI) * 1.65) : 0
  const open = clamp01(blink * (1 - happy * 1.15))
  const closedOp = clamp01((0.32 - open) / 0.32)
  const closedY = EYE_Y + 9 - 4 * happy
  const closedCurve = mix(4, -9, happy)

  const lookX = (active ? track(loop(t, 7200) * 7200, GLANCE_X) : 0) * (1 - hoverW * 0.6)
  const lookY = -0.8 * hoverW

  // Yuzu citrus on crown: hops with follow-through when booped + gentle leaf breeze
  // Every 3rd click triggers a full 360-degree citrus spin in mid-air
  const isSuperBoop = isBooping && boopCount.value > 0 && boopCount.value % 3 === 0
  const yuzuSpin = isSuperBoop
    ? 360 * EASE_IN_OUT(clamp01((boopQ - 0.08) / 0.68))
    : isBooping
      ? 14 * Math.sin(boopQ * Math.PI * 2) * (1 - boopQ)
      : 0
  const yuzuDy = isBooping ? track(boopElapsed, BOOP_YUZU_Y) * (isSuperBoop ? 1.25 : 1) : 0
  const yuzuRot = (active ? 1.8 * wave(t, 3400, 0.25) : 0) + hoverW * 3.5 + yuzuSpin
  const leafRot =
    -22 +
    (active ? 3.5 * wave(t, 2600, 0.1) : 0) +
    hoverW * -5 +
    (isBooping ? -18 * Math.sin(boopQ * Math.PI * 3) * (1 - boopQ) : 0)

  // Front paws lift slightly during the hop peak
  const pawLift = isBooping ? Math.max(0, -boopHeadDy * 0.55) : 0

  // Citrus aroma sparkles during a boop
  const sparks = ([-1, 0, 1] as const).map((dir, i) => {
    const localQ = clamp01((boopQ - 0.12 - i * 0.06) / 0.72)
    const op = isBooping ? bell(localQ) : 0
    const sxPos = dir * (22 + 20 * localQ)
    const syPos = -58 - 18 * localQ - (i === 1 ? 8 * localQ : 0)
    const scale = 0.65 + 0.55 * Math.sin(localQ * Math.PI)
    return {
      op,
      tf: `translate(${sxPos} ${syPos}) scale(${scale})`,
      color: i === 0 ? C.yuzu : i === 1 ? C.sparkOrange : C.leaf,
    }
  })

  // Staggered letter wave on Y-U-Z-U during a boop + follow-through pop on .auto pill
  const letters = [0, 1, 2, 3].map((i) => {
    if (!isBooping) return 'translate(0 0)'
    const lq = clamp01((boopElapsed - i * 55) / 420)
    const dy = -2.4 * Math.sin(lq * Math.PI)
    return `translate(0 ${dy.toFixed(2)})`
  })
  const badgeQ = isBooping ? clamp01((boopElapsed - 210) / 360) : 0
  const badgeScale = 1 + 0.08 * Math.sin(badgeQ * Math.PI)
  const badgeDy = -1.4 * Math.sin(badgeQ * Math.PI)
  const badgeStyle = isBooping
    ? { transform: `translateY(${badgeDy.toFixed(2)}px) scale(${badgeScale.toFixed(3)})` }
    : undefined

  return {
    body: {
      x: 100 - bodyW / 2,
      y: 150 - bodyH,
      w: bodyW,
      h: bodyH,
      rx: Math.min(bodyW, bodyH) * 0.46,
    },
    headTf: `translate(100 ${headY}) rotate(${headTilt} 0 30)`,
    earL,
    earR,
    open,
    closedOp,
    closedLeft: `M -28 ${closedY} Q -20 ${closedY + closedCurve} -12 ${closedY}`,
    closedRight: `M 12 ${closedY} Q 20 ${closedY + closedCurve} 28 ${closedY}`,
    lookX,
    lookY,
    cheekY: 6 - 1.8 * happy,
    cheekScale: 1 + 0.12 * happy,
    mouthD:
      happy > 0.2
        ? 'M -7.4 22.5 Q 0 28.4 7.4 22.5 Q 0 28.4 -7.4 22.5 Z'
        : 'M -6.2 23 Q 0 27.2 6.2 23 Q 0 27.2 -6.2 23 Z',
    yuzuTf: `translate(0 ${-46 + yuzuDy}) rotate(${yuzuRot})`,
    leafTf: `rotate(${leafRot} 1.5 -15)`,
    pawY: 136 - pawLift,
    sparks,
    boopEnv,
    letters,
    badgeStyle,
  }
})
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
    <!-- Unified Capybara Yuzu Mark (Interactive & Alive via rossark-motion-skill) -->
    <svg
      v-if="variant === 'mascot'"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="32 14 136 140"
      fill="none"
      :width="resolvedSize"
      :height="resolvedSize"
      aria-hidden="true"
      class="pointer-events-none shrink-0 overflow-visible select-none"
    >
      <defs>
        <clipPath v-for="(cx, i) in EYES" :id="`${uid}-eye${i}`" :key="`e${i}`">
          <rect :x="cx - 10" :y="EYE_Y - 13" width="20" height="26" rx="10" />
        </clipPath>
        <clipPath v-for="(cx, i) in EYES" :id="`${uid}-lid${i}`" :key="`l${i}`">
          <rect :x="cx - 12" :y="EYE_Y - 15" width="24" height="30" rx="12" />
        </clipPath>
      </defs>

      <!-- Chubby loaf body with volume-preserving breathing & boop bounce -->
      <rect
        :x="anim.body.x"
        :y="anim.body.y"
        :width="anim.body.w"
        :height="anim.body.h"
        :rx="anim.body.rx"
        :fill="C.skin"
      />

      <!-- Head group -->
      <g :transform="anim.headTf">
        <!-- Ears -->
        <rect
          x="-38"
          y="-45"
          width="15"
          height="18"
          rx="7.5"
          :fill="C.skinShade"
          :transform="`rotate(${anim.earL} -30 -30)`"
        />
        <rect
          x="23"
          y="-45"
          width="15"
          height="18"
          rx="7.5"
          :fill="C.skinShade"
          :transform="`rotate(${anim.earR} 30 -30)`"
        />

        <!-- Head: rounded tombstone block (88 x 76, rx=34) -->
        <rect x="-44" y="-38" width="88" height="76" rx="34" :fill="C.skin" />

        <!-- Signature Yuzu citrus seated on crown of head -->
        <g :transform="anim.yuzuTf">
          <rect
            x="1.5"
            y="-18"
            width="13"
            height="6.4"
            rx="3.2"
            :fill="C.leaf"
            :transform="anim.leafTf"
          />
          <circle cx="0" cy="-2" r="11.5" :fill="C.yuzu" />
          <path
            d="M 11.5 -2 A 11.5 11.5 0 0 1 -4.3 8.6 A 14.4 14.4 0 0 1 11.5 -2 Z"
            :fill="C.yuzuShade"
          />
          <rect x="-6.5" y="-8.5" width="4" height="6.4" rx="2" :fill="C.white" />
        </g>

        <!-- Citrus aroma droplets emitted on boop -->
        <g
          v-for="(sp, si) in anim.sparks"
          v-show="sp.op > 0.02"
          :key="`sp${si}`"
          :opacity="sp.op"
          :transform="sp.tf"
        >
          <circle cx="0" cy="0" r="3.4" :fill="sp.color" />
        </g>

        <!-- Muzzle (64 x 36, rx=17) -->
        <rect x="-32" y="0" width="64" height="36" rx="17" :fill="C.muzzle" />

        <!-- Cheeks -->
        <rect
          x="-42"
          :y="anim.cheekY"
          width="11"
          height="7"
          rx="3.5"
          :fill="C.cheek"
          :transform="`scale(${anim.cheekScale})`"
          style="transform-box: fill-box; transform-origin: center"
        />
        <rect
          x="31"
          :y="anim.cheekY"
          width="11"
          height="7"
          rx="3.5"
          :fill="C.cheek"
          :transform="`scale(${anim.cheekScale})`"
          style="transform-box: fill-box; transform-origin: center"
        />

        <!-- Nostrils + smile -->
        <rect x="-9" y="8" width="6" height="8" rx="3" :fill="C.feature" />
        <rect x="3" y="8" width="6" height="8" rx="3" :fill="C.feature" />
        <path
          :d="anim.mouthD"
          :fill="C.feature"
          :stroke="C.feature"
          stroke-width="3"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- Live eyes (blink + glance + happy arch on boop) -->
        <g v-for="(cx, i) in EYES" :key="`eye${i}`">
          <g v-show="anim.open > 0.04">
            <rect :x="cx - 10" :y="EYE_Y - 13" width="20" height="26" rx="10" :fill="C.white" />
            <g :clip-path="`url(#${uid}-eye${i})`">
              <rect
                :x="cx - 5 + anim.lookX"
                :y="EYE_Y - 8.5 + anim.lookY"
                width="10"
                height="15"
                rx="5"
                :fill="C.pupil"
              />
              <circle
                :cx="cx - 1.5 + anim.lookX"
                :cy="EYE_Y - 4.5 + anim.lookY"
                r="2.2"
                :fill="C.white"
              />
            </g>
            <g :clip-path="`url(#${uid}-lid${i})`">
              <rect
                :x="cx - 14"
                :y="EYE_Y - 17"
                width="28"
                :height="Math.max(4.2, 28 * (1 - anim.open))"
                :fill="C.skin"
              />
              <rect :x="cx - 12" :y="EYE_Y + 11.5" width="24" height="3.5" :fill="C.skin" />
            </g>
          </g>
          <path
            v-show="anim.closedOp > 0.01"
            :d="i === 0 ? anim.closedLeft : anim.closedRight"
            :opacity="anim.closedOp"
            fill="none"
            :stroke="C.feature"
            stroke-width="3.5"
            stroke-linecap="round"
          />
        </g>
      </g>

      <!-- Front paws -->
      <rect x="74" :y="anim.pawY" width="22" height="14" rx="7" :fill="C.muzzle" />
      <rect x="104" :y="anim.pawY" width="22" height="14" rx="7" :fill="C.muzzle" />
    </svg>

    <!-- Unified Wordmark & Institutional Descriptor Lockup -->
    <div v-if="layout !== 'mark'" class="pointer-events-none flex min-w-0 flex-col gap-1">
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
            <path
              :transform="anim.letters[0]"
              d="M 4.5 4.5 L 13.5 16.5 L 22.5 4.5 M 13.5 16.5 L 13.5 27.5"
            />
            <!-- U -->
            <path
              :transform="anim.letters[1]"
              d="M 30.5 4.5 L 30.5 18.5 A 9 9 0 0 0 48.5 18.5 L 48.5 4.5"
            />
            <!-- Z -->
            <path :transform="anim.letters[2]" d="M 58.5 4.5 L 76.5 4.5 L 58.5 27.5 L 76.5 27.5" />
            <!-- U -->
            <path
              :transform="anim.letters[3]"
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
          :style="anim.badgeStyle"
          class="bg-surface-inset text-text-primary border-border inline-flex origin-center items-center rounded-full border px-2 py-0.5 text-[11px] leading-none font-semibold tracking-tight uppercase"
        >
          Report
        </span>

        <span
          v-else
          :style="anim.badgeStyle"
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
        <span class="truncate">{{ resolvedSubtitle }}</span>
      </span>
    </div>
  </div>
</template>
