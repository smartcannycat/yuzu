<script setup lang="ts">
import { computed, onMounted, ref, useId, type CSSProperties } from 'vue'
import { useLook } from './looks'
import './phone.css'

export type PhoneFrame =
  | 'pro'
  | 'photo'
  | 'bezel'
  | 'soft'
  | 'bare'
  | 'silver'
  | 'clay'
  | 'outline'
  | 'android'

export interface PhoneProps {
  width: number
  frame?: PhoneFrame
  time?: string
  island?: boolean
  status?: boolean
  dark?: boolean
  wallpaper?: string
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<PhoneProps>(), {
  frame: 'pro',
  time: '9:41',
  island: undefined,
  status: undefined,
})

const IPHONE = { w: 402, h: 874, r: 64 }
const CORNER = { a: 71, n: 2.31 }
const SOFT = { w: 393, h: 829, r: 42 }
const PIXEL = { w: 412, h: 915, r: 38 }

const FRAMES: Record<PhoneFrame, { band: number; glass: number }> = {
  pro: { band: 3, glass: 10 },
  photo: { band: 0, glass: 16 },
  bezel: { band: 0, glass: 12 },
  soft: { band: 0, glass: 12.5 },
  bare: { band: 0, glass: 0 },
  silver: { band: 4, glass: 9 },
  clay: { band: 0, glass: 16 },
  outline: { band: 0, glass: 8 },
  android: { band: 2, glass: 9 },
}

const BANDS: Partial<Record<PhoneFrame, [number, string][]>> = {
  pro: [[13, 'band'], [10, 'var(--ss-phone-rim)'], [9.25, 'var(--ss-phone-glass)']],
  silver: [[13, 'band'], [9, 'var(--ss-phone-glass)']],
  bezel: [[12, 'var(--ss-phone-glass)']],
  clay: [[16, 'clay'], [1, 'var(--ss-phone-seam)']],
}

function superellipsePath(w: number, h: number, a: number, n: number) {
  const steps = 32
  const e = 2 / n
  const pts: string[] = []
  const corners: [number, number, number, number][] = [
    [w - a, a, 1, -1],
    [w - a, h - a, 1, 1],
    [a, h - a, -1, 1],
    [a, a, -1, -1],
  ]
  corners.forEach(([cx, cy, sx, sy], c) => {
    for (let i = 0; i <= steps; i++) {
      const t = (i / steps) * (Math.PI / 2)
      const u = c % 2 === 0 ? Math.sin(t) : Math.cos(t)
      const v = c % 2 === 0 ? Math.cos(t) : Math.sin(t)
      pts.push(`${(cx + sx * a * Math.pow(u, e)).toFixed(2)} ${(cy + sy * a * Math.pow(v, e)).toFixed(2)}`)
    }
  })
  return `M${pts.join('L')}Z`
}

const photoRef = ref<HTMLSpanElement | null>(null)
const photoOk = ref(true)

onMounted(() => {
  if (props.frame !== 'photo' || !photoRef.value) return
  const bg = getComputedStyle(photoRef.value).backgroundImage
  const url = bg.match(/url\(["']?([^"')]+)["']?\)/)?.[1]
  if (!url) {
    photoOk.value = false
    return
  }
  const img = new Image()
  img.onerror = () => {
    photoOk.value = false
  }
  img.src = url
})

const effectiveFrame = computed<PhoneFrame>(() =>
  props.frame === 'photo' && !photoOk.value ? 'pro' : props.frame,
)

const look = useLook()
const SCREEN = computed(() =>
  effectiveFrame.value === 'android' ? PIXEL : effectiveFrame.value === 'soft' ? SOFT : IPHONE,
)
const edge = computed(() => {
  const { band, glass } = FRAMES[effectiveFrame.value]
  return band + glass
})

const s = computed(() => props.width / (SCREEN.value.w + edge.value * 2))
const pt = (n: number) => n * s.value

const rawId = useId()
const id = computed(() => rawId.replace(/:/g, ''))

const ios = computed(() => effectiveFrame.value !== 'android' && effectiveFrame.value !== 'soft')
const outline = computed(() =>
  ios.value ? superellipsePath(pt(SCREEN.value.w), pt(SCREEN.value.h), pt(CORNER.a), CORNER.n) : null,
)
const bands = computed(() => BANDS[effectiveFrame.value])
const chrome = computed(
  () =>
    effectiveFrame.value === 'pro' ||
    effectiveFrame.value === 'photo' ||
    effectiveFrame.value === 'bezel' ||
    effectiveFrame.value === 'silver' ||
    effectiveFrame.value === 'android',
)

const showIsland = computed(() => props.island ?? (chrome.value && effectiveFrame.value !== 'photo'))
const showStatus = computed(() => props.status ?? chrome.value)

const phoneStyle = computed<CSSProperties>(() => {
  const { band } = FRAMES[effectiveFrame.value]
  return {
    width: `${props.width}px`,
    height: `${pt(SCREEN.value.h + edge.value * 2)}px`,
    padding: `${pt(band)}px`,
    borderRadius: `${pt(SCREEN.value.r + edge.value)}px`,
    ['--ps' as any]: `${s.value}px`,
    ...props.style,
  }
})

const glassStyle = computed(() => {
  const { glass } = FRAMES[effectiveFrame.value]
  return {
    padding: `${pt(glass)}px`,
    borderRadius: `${pt(SCREEN.value.r + glass)}px`,
  }
})

const windowStyle = computed(() => ({
  width: `${pt(SCREEN.value.w)}px`,
  height: `${pt(SCREEN.value.h)}px`,
  borderRadius: outline.value ? undefined : `${pt(SCREEN.value.r)}px`,
  clipPath: outline.value ? `path('${outline.value}')` : undefined,
}))

const screenStyle = computed<CSSProperties>(() => ({
  width: `${SCREEN.value.w}px`,
  height: `${SCREEN.value.h}px`,
  transform: `scale(${s.value})`,
  ['--ss-screen-r' as any]: `${SCREEN.value.r}px`,
  ...(props.wallpaper ? { background: props.wallpaper } : null),
}))
</script>

<template>
  <div
    :class="['ss-phone', props.className, props.class]"
    :data-frame="effectiveFrame"
    :data-dark="props.dark || undefined"
    :style="phoneStyle"
  >
    <svg
      v-if="(bands || effectiveFrame === 'outline') && outline"
      class="ss-phone__bands"
      width="100%"
      height="100%"
      aria-hidden="true"
    >
      <defs>
        <linearGradient :id="`${id}-band`" x1="0.2" y1="0" x2="0.8" y2="1">
          <stop
            v-for="(o, i) in [0, 0.22, 0.48, 0.74, 1]"
            :key="o"
            :offset="o"
            :style="{ stopColor: `var(--ss-phone-band-${i + 1})` }"
          />
        </linearGradient>
        <linearGradient :id="`${id}-clay`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" style="stop-color: var(--ss-phone-clay-top)" />
          <stop offset="1" style="stop-color: var(--ss-phone-clay-bottom)" />
        </linearGradient>
        <mask
          v-if="effectiveFrame === 'outline'"
          :id="`${id}-ring`"
          maskUnits="userSpaceOnUse"
          x="-50%"
          y="-50%"
          width="200%"
          height="200%"
        >
          <path :d="outline" fill="none" stroke="#fff" :stroke-width="pt(16)" />
          <path :d="outline" fill="none" stroke="#000" :stroke-width="pt(16) - 2" />
        </mask>
      </defs>
      <g :transform="`translate(${pt(edge)} ${pt(edge)})`" stroke-linejoin="round">
        <template v-if="effectiveFrame === 'outline'">
          <rect
            :x="-pt(9)"
            :y="-pt(9)"
            :width="pt(SCREEN.w + 18)"
            :height="pt(SCREEN.h + 18)"
            :mask="`url(#${id}-ring)`"
            style="fill: var(--ss-phone-line)"
          />
          <path
            :d="outline"
            fill="none"
            stroke-width="2"
            style="stroke: var(--ss-line, rgba(0, 0, 0, 0.06))"
          />
        </template>
        <template v-else-if="bands">
          <path
            v-for="([d, paint]) in bands"
            :key="d"
            :d="outline"
            fill="none"
            :stroke-width="pt(d * 2)"
            :stroke="paint === 'band' || paint === 'clay' ? `url(#${id}-${paint})` : undefined"
            :style="paint === 'band' || paint === 'clay' ? undefined : { stroke: paint }"
          />
        </template>
      </g>
    </svg>

    <div class="ss-phone__glass" :style="glassStyle">
      <div class="ss-phone__window" :style="windowStyle">
        <div class="ss-phone__screen" :style="screenStyle">
          <div v-if="showStatus" class="ss-phone__status">
            <span class="ss-phone__time">
              <span v-if="look.fidelity === 'minimal'" class="ss-phone__time-bar" />
              <template v-else>{{ props.time }}</template>
            </span>
            <span class="ss-phone__glyphs">
              <!-- Signal -->
              <svg viewBox="0 0 20.33 13.67" width="20.33" height="13.67" class="ss-phone__glyph ss-phone__signal">
                <rect
                  v-for="(hVal, i) in [6.33, 8.67, 11, 13.67]"
                  :key="i"
                  :x="i * 5.667"
                  :y="13.67 - hVal"
                  width="3.333"
                  :height="hVal"
                  rx="1.667"
                  fill="currentColor"
                />
              </svg>
              <!-- Wifi -->
              <svg viewBox="0 0 19.33 14.33" width="19.33" height="14.33" class="ss-phone__glyph ss-phone__wifi">
                <path fill-rule="evenodd" fill="currentColor" d="M0.415933 5.54283C0.902185 6.04412 1.66017 5.95818 2.27513 5.41393C4.30595 3.58064 6.83731 2.63535 9.66901 2.63535C12.5007 2.63535 15.0464 3.60928 17.0629 5.41393C17.6636 5.97251 18.4215 6.0298 18.9221 5.54283C19.4226 5.02722 19.4942 4.2538 18.9793 3.70954C16.8341 1.51819 13.3302 0 9.66901 0C6.00783 0 2.48965 1.53251 0.358727 3.72387C-0.156127 4.2538 -0.0989213 5.02722 0.415933 5.55715L0.415933 5.54283ZM3.94841 9.13779C4.50617 9.68205 5.22124 9.62476 5.85051 9.10915C6.88022 8.29276 8.25316 7.73418 9.66901 7.7485C11.0706 7.7485 12.4435 8.29276 13.4875 9.12347C14.1168 9.63908 14.8605 9.66773 15.4039 9.12347C15.9331 8.57921 16.0189 7.7485 15.4611 7.23289C14.0739 5.98683 11.9859 5.11315 9.68332 5.11315C7.38077 5.11315 5.27845 5.98683 3.9055 7.23289C3.41925 7.69121 3.31914 8.47896 3.96271 9.13779L3.94841 9.13779ZM8.72511 13.8929C9.34008 14.4801 9.98365 14.4801 10.5986 13.8929L11.757 12.7757C12.372 12.1742 12.5007 11.4151 11.7999 10.8995C11.2136 10.4841 10.4699 10.212 9.66901 10.212C8.86813 10.212 8.11015 10.4841 7.53809 10.9138C6.83731 11.4151 6.98033 12.1885 7.59529 12.7757L8.73942 13.8929L8.72511 13.8929Z" />
              </svg>
              <!-- Battery -->
              <svg viewBox="0 0 29.33 13.67" width="29.33" height="13.67" class="ss-phone__glyph ss-phone__battery">
                <path fill="currentColor" d="M0 6.4C0 4.15979 0 3.03969 0.435974 2.18404C0.819467 1.43139 1.43139 0.819467 2.18404 0.435974C3.03969 0 4.15979 0 6.4 0L19.933 0C22.1732 0 23.2933 0 24.149 0.435974C24.9016 0.819467 25.5135 1.43139 25.897 2.18404C26.333 3.03969 26.333 4.15979 26.333 6.4L26.333 7.26666C26.333 9.50687 26.333 10.627 25.897 11.4826C25.5135 12.2353 24.9016 12.8472 24.149 13.2307C23.2933 13.6667 22.1732 13.6667 19.933 13.6667L6.4 13.6667C4.15979 13.6667 3.03969 13.6667 2.18404 13.2307C1.43139 12.8472 0.819467 12.2353 0.435974 11.4826C0 10.627 0 9.50687 0 7.26666L0 6.4Z" />
                <path fill-rule="evenodd" fill="currentColor" transform="translate(27.33 4.33)" d="M0 0L0 5C0.601505 4.8625 2 3.75 2 2.5C2 1.25 0.601505 0.1375 0 0Z" />
              </svg>
            </span>
          </div>

          <span v-if="showIsland" class="ss-phone__island" />
          <div class="ss-phone__content" :data-status="showStatus || undefined">
            <slot />
          </div>
          <span v-if="chrome" class="ss-phone__home" />
        </div>
      </div>
    </div>

    <span
      v-if="effectiveFrame === 'photo'"
      ref="photoRef"
      class="ss-phone__photo"
      :style="{ left: `${pt(-8)}px`, top: `${pt(-7)}px`, width: `${pt(450)}px`, height: `${pt(920)}px` }"
    />
  </div>
</template>
