<script setup lang="ts">
import { useId } from 'vue'

import type { CapyFramePose } from './capyRigFrame'
import { MASCOT_COLORS } from './palette'
import YuzuCitrusSvg from './YuzuCitrusSvg.vue'

defineProps<{
  pose: CapyFramePose
}>()

const uid = useId()
</script>

<template>
  <g>
    <defs>
      <clipPath :id="`${uid}-sheet-clip`">
        <rect x="44" y="102" width="48" height="38" rx="6" />
      </clipPath>
    </defs>

    <!-- Prop 1A: Auction Sheet with Farpost Orange Scan Beam (THINKING) -->
    <g
      v-if="pose.sheetOp > 0.01"
      :opacity="pose.sheetOp"
      :transform="`translate(0 ${pose.sheetY}) rotate(-4 68 122)`"
    >
      <rect x="42" y="100" width="52" height="42" rx="7" :fill="MASCOT_COLORS.sheetBorder" />
      <rect x="44" y="101" width="48" height="39" rx="6" :fill="MASCOT_COLORS.sheetBg" />
      <rect x="48" y="105" width="22" height="4" rx="2" :fill="MASCOT_COLORS.scanOrange" />
      <rect x="74" y="105" width="14" height="4" rx="2" :fill="MASCOT_COLORS.sheetLine" />
      <rect x="48" y="113" width="24" height="15" rx="4" :fill="MASCOT_COLORS.loupeGlass" />
      <rect x="52" y="116" width="16" height="9" rx="3" :fill="MASCOT_COLORS.loupeEdge" />
      <rect x="75" y="113" width="13" height="3.5" rx="1.75" :fill="MASCOT_COLORS.sheetLine" />
      <rect x="75" y="119" width="11" height="3.5" rx="1.75" :fill="MASCOT_COLORS.sheetLine" />
      <rect x="48" y="131" width="40" height="4" rx="2" :fill="MASCOT_COLORS.sheetLine" />
      <g :clip-path="`url(#${uid}-sheet-clip)`">
        <rect
          x="42"
          :y="pose.scanY - 4"
          width="52"
          height="8"
          :fill="MASCOT_COLORS.scanGlow"
          opacity="0.55"
        />
        <rect
          x="42"
          :y="pose.scanY"
          width="52"
          height="3"
          rx="1.5"
          :fill="MASCOT_COLORS.scanOrange"
        />
      </g>
    </g>

    <!-- Prop 1B: Inspector Loupe (drawn before right paw so paw grips handle) -->
    <g v-if="pose.loupeOp > 0.01" :opacity="pose.loupeOp" :transform="pose.loupeTf">
      <rect
        :x="pose.pawR.x - 3"
        :y="pose.pawR.y - 26"
        width="6"
        height="34"
        rx="3"
        :fill="MASCOT_COLORS.feature"
      />
      <circle :cx="pose.pawR.x" :cy="pose.pawR.y - 34" r="16" :fill="MASCOT_COLORS.loupeRim" />
      <circle :cx="pose.pawR.x" :cy="pose.pawR.y - 34" r="11.5" :fill="MASCOT_COLORS.loupeGlass" />
      <rect
        :x="pose.pawR.x - 6"
        :y="pose.pawR.y - 41"
        width="4"
        height="9"
        rx="2"
        :fill="MASCOT_COLORS.white"
        :transform="`rotate(-25 ${pose.pawR.x - 4} ${pose.pawR.y - 37})`"
      />
    </g>

    <!-- Prop 2: Green Verdict Flag with Yuzu Citrus Finial (GREEN) -->
    <g v-if="pose.flagOp > 0.01" :opacity="pose.flagOp" :transform="pose.flagTf">
      <g transform="translate(2 -80)">
        <rect x="0" y="0" width="50" height="35" rx="9" :fill="MASCOT_COLORS.leaf" />
        <path
          d="M 15 17.5 L 22.5 24.5 L 36.5 11"
          fill="none"
          :stroke="MASCOT_COLORS.white"
          stroke-width="5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>
      <rect x="-3.5" y="-84" width="7" height="94" rx="3.5" :fill="MASCOT_COLORS.feature" />
      <YuzuCitrusSvg variant="finial" :transform="`translate(0 -84) rotate(${pose.yuzuRock})`" />
    </g>

    <!-- Prop 3: Yellow Caution Inspector Paddle (YELLOW) -->
    <g v-if="pose.cautionOp > 0.01" :opacity="pose.cautionOp" :transform="pose.cautionTf">
      <rect x="-3.5" y="-68" width="7" height="78" rx="3.5" :fill="MASCOT_COLORS.feature" />
      <rect x="-20" y="-88" width="40" height="40" rx="12" :fill="MASCOT_COLORS.yuzu" />
      <rect x="-3" y="-79" width="6" height="16" rx="3" :fill="MASCOT_COLORS.pupil" />
      <circle cx="0" cy="-56" r="3.4" :fill="MASCOT_COLORS.pupil" />
      <g v-if="pose.cautionPulse > 0.02" :opacity="pose.cautionPulse">
        <path
          d="M 26 -78 A 18 18 0 0 1 26 -58"
          fill="none"
          :stroke="MASCOT_COLORS.scanOrange"
          stroke-width="3.2"
          stroke-linecap="round"
        />
      </g>
    </g>

    <!-- Prop 4: Red Stop-Factor Traffic Light (RED) -->
    <g v-if="pose.sigOp > 0.01" :opacity="pose.sigOp" :transform="pose.sigTf">
      <rect x="-4" y="-32" width="8" height="46" rx="4" :fill="MASCOT_COLORS.feature" />
      <rect x="-22" y="-102" width="44" height="76" rx="17" :fill="MASCOT_COLORS.housing" />
      <circle cx="0" cy="-63" r="9.5" :fill="MASCOT_COLORS.lampOff" />
      <circle cx="0" cy="-42" r="9.5" :fill="MASCOT_COLORS.lampOff" />
      <circle cx="0" cy="-84" r="11.5" :fill="MASCOT_COLORS.redLight" />
      <circle cx="-3.5" cy="-87.5" r="3.2" :fill="MASCOT_COLORS.redShine" />
      <g
        v-for="(ring, idx) in pose.redRings"
        v-show="ring.op > 0.02"
        :key="`rr${idx}`"
        :opacity="ring.op"
      >
        <path
          :d="`M ${-26 - ring.offset} -96 A 22 22 0 0 0 ${-26 - ring.offset} -70`"
          fill="none"
          :stroke="MASCOT_COLORS.redGlow"
          stroke-width="3.5"
          stroke-linecap="round"
        />
        <path
          :d="`M ${26 + ring.offset} -96 A 22 22 0 0 1 ${26 + ring.offset} -70`"
          fill="none"
          :stroke="MASCOT_COLORS.redGlow"
          stroke-width="3.5"
          stroke-linecap="round"
        />
      </g>
    </g>

    <!-- Paws (drawn on top of prop handles so grip reads cleanly) -->
    <rect
      :x="pose.pawL.x - pose.pawL.w / 2"
      :y="pose.pawL.y - pose.pawL.h / 2"
      :width="pose.pawL.w"
      :height="pose.pawL.h"
      :rx="pose.pawL.h / 2"
      :fill="pose.pawL.fill"
      :transform="`rotate(${pose.pawL.rot} ${pose.pawL.x} ${pose.pawL.y})`"
    />
    <rect
      :x="pose.pawR.x - pose.pawR.w / 2"
      :y="pose.pawR.y - pose.pawR.h / 2"
      :width="pose.pawR.w"
      :height="pose.pawR.h"
      :rx="pose.pawR.h / 2"
      :fill="pose.pawR.fill"
      :transform="`rotate(${pose.pawR.rot} ${pose.pawR.x} ${pose.pawR.y})`"
    />

    <!-- Prop 5: Floating Question Marks on OCR Error (ERROR) -->
    <g
      v-for="(q, i) in pose.questions"
      v-show="q.op > 0.01"
      :key="`q${i}`"
      :opacity="q.op"
      :transform="q.tf"
    >
      <path
        d="M -5 -8 A 5.5 5.5 0 1 1 3.5 -2.5 C 1.5 -1 0 0.5 0 3"
        fill="none"
        :stroke="q.color"
        stroke-width="3.5"
        stroke-linecap="round"
      />
      <circle cx="0" cy="8.5" r="2" :fill="q.color" />
    </g>

    <!-- Zzz Glyphs (SLEEPING) -->
    <path
      v-for="(z, i) in pose.zzz"
      v-show="z.op > 0.01"
      :key="`z${i}`"
      :d="z.d"
      :opacity="z.op"
      fill="none"
      :stroke="z.color"
      stroke-width="3"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </g>
</template>
