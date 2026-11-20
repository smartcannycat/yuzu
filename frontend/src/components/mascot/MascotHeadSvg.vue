<script setup lang="ts">
import { useId } from 'vue'

import { MASCOT_COLORS, MASCOT_EYES_X, MASCOT_EYE_Y } from './palette'

export interface MascotEyeFrame {
  cx: number
  pupilX: number
  pupilY: number
  lidH: number
  lowY: number
  lowH: number
  lidTf?: string
  closed: string
}

interface Props {
  headTf: string
  earL: number
  earR: number
  open: number
  closedOp: number
  eyes: readonly MascotEyeFrame[]
  cheekY: number
  cheekScale?: number
  mouthD: string
}

withDefaults(defineProps<Props>(), {
  cheekScale: 1,
})

const uid = useId()
</script>

<template>
  <g :transform="headTf">
    <defs>
      <clipPath v-for="(cx, i) in MASCOT_EYES_X" :id="`${uid}-eye${i}`" :key="`e${i}`">
        <rect :x="cx - 10" :y="MASCOT_EYE_Y - 13" width="20" height="26" rx="10" />
      </clipPath>
      <clipPath v-for="(cx, i) in MASCOT_EYES_X" :id="`${uid}-lid${i}`" :key="`l${i}`">
        <rect :x="cx - 12" :y="MASCOT_EYE_Y - 15" width="24" height="30" rx="12" />
      </clipPath>
    </defs>

    <!-- Ears: rounded capsules one shade darker -->
    <rect
      x="-38"
      y="-45"
      width="15"
      height="18"
      rx="7.5"
      :fill="MASCOT_COLORS.skinShade"
      :transform="`rotate(${earL} -30 -30)`"
    />
    <rect
      x="23"
      y="-45"
      width="15"
      height="18"
      rx="7.5"
      :fill="MASCOT_COLORS.skinShade"
      :transform="`rotate(${earR} 30 -30)`"
    />

    <!-- Head: rounded tombstone block (88 x 76, rx=34) -->
    <rect x="-44" y="-38" width="88" height="76" rx="34" :fill="MASCOT_COLORS.skin" />

    <!-- Optional crown graphics (e.g. BrandLogo Yuzu citrus + sparkles) -->
    <slot name="crown" />

    <!-- Muzzle (64 x 36, rx=17) -->
    <rect x="-32" y="0" width="64" height="36" rx="17" :fill="MASCOT_COLORS.muzzle" />

    <!-- Cheeks -->
    <rect
      x="-42"
      :y="cheekY"
      width="11"
      height="7"
      rx="3.5"
      :fill="MASCOT_COLORS.cheek"
      :transform="cheekScale !== 1 ? `scale(${cheekScale})` : undefined"
      :style="cheekScale !== 1 ? 'transform-box: fill-box; transform-origin: center' : undefined"
    />
    <rect
      x="31"
      :y="cheekY"
      width="11"
      height="7"
      rx="3.5"
      :fill="MASCOT_COLORS.cheek"
      :transform="cheekScale !== 1 ? `scale(${cheekScale})` : undefined"
      :style="cheekScale !== 1 ? 'transform-box: fill-box; transform-origin: center' : undefined"
    />

    <!-- Nostrils + morphing mouth -->
    <rect x="-9" y="8" width="6" height="8" rx="3" :fill="MASCOT_COLORS.feature" />
    <rect x="3" y="8" width="6" height="8" rx="3" :fill="MASCOT_COLORS.feature" />
    <path
      :d="mouthD"
      :fill="MASCOT_COLORS.feature"
      :stroke="MASCOT_COLORS.feature"
      stroke-width="3"
      stroke-linejoin="round"
      stroke-linecap="round"
    />

    <!-- Live eyes: white pills, clipped pupils, clipped skin lids +2 larger -->
    <g v-for="(eye, i) in eyes" :key="`eye${i}`">
      <g v-show="open > 0.04">
        <rect
          :x="eye.cx - 10"
          :y="MASCOT_EYE_Y - 13"
          width="20"
          height="26"
          rx="10"
          :fill="MASCOT_COLORS.white"
        />
        <g :clip-path="`url(#${uid}-eye${i})`">
          <rect
            :x="eye.pupilX"
            :y="eye.pupilY"
            width="10"
            height="15"
            rx="5"
            :fill="MASCOT_COLORS.pupil"
          />
          <circle :cx="eye.pupilX + 3.5" :cy="eye.pupilY + 4" r="2.2" :fill="MASCOT_COLORS.white" />
        </g>
        <g :clip-path="`url(#${uid}-lid${i})`">
          <rect
            :x="eye.cx - 14"
            :y="MASCOT_EYE_Y - 17"
            width="28"
            :height="eye.lidH"
            :fill="MASCOT_COLORS.skin"
            :transform="eye.lidTf"
          />
          <rect
            :x="eye.cx - 12"
            :y="eye.lowY"
            width="24"
            :height="eye.lowH"
            :fill="MASCOT_COLORS.skin"
          />
        </g>
      </g>
      <path
        v-show="closedOp > 0.01"
        :d="eye.closed"
        :opacity="closedOp"
        fill="none"
        :stroke="MASCOT_COLORS.feature"
        stroke-width="3.5"
        stroke-linecap="round"
      />
    </g>
  </g>
</template>
