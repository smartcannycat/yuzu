<script setup lang="ts">
import { computed } from 'vue'

import type { BodyPanel, NormalizedDefect } from '@/types/api'

interface Props {
  defects: NormalizedDefect[]
  selectedPanel: BodyPanel | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:selectedPanel': [panel: BodyPanel | null]
}>()

interface PanelPinCoord {
  x: number
  y: number
}

const PANEL_COORDS: Record<BodyPanel, PanelPinCoord> = {
  front_bumper: { x: 140, y: 38 },
  hood: { x: 140, y: 92 },
  windshield: { x: 140, y: 145 },
  roof: { x: 140, y: 220 },
  tailgate: { x: 140, y: 310 },
  rear_bumper: { x: 140, y: 364 },
  front_left_fender: { x: 55, y: 92 },
  front_right_fender: { x: 225, y: 92 },
  front_left_door: { x: 60, y: 169 },
  front_right_door: { x: 220, y: 169 },
  rear_left_door: { x: 60, y: 251 },
  rear_right_door: { x: 220, y: 251 },
  rear_left_quarter: { x: 60, y: 318 },
  rear_right_quarter: { x: 220, y: 318 },
  left_sill: { x: 26, y: 208 },
  right_sill: { x: 254, y: 208 },
}

const DEFECT_BY_PANEL = computed(() => {
  const map = new Map<BodyPanel, NormalizedDefect>()
  for (const defect of props.defects) {
    if (!map.has(defect.panel_id)) {
      map.set(defect.panel_id, defect)
    }
  }
  return map
})

const uniquePinDefects = computed(() => Array.from(DEFECT_BY_PANEL.value.values()))

function getPinTone(defect: NormalizedDefect): 'danger' | 'warning' | 'info' {
  const code = defect.raw_code.toUpperCase()
  if (code.includes('XX') || code.includes('X') || (defect.severity ?? 0) >= 3) {
    return 'danger'
  }
  if (code.includes('W') || code.includes('S') || (defect.severity ?? 0) === 2) {
    return 'warning'
  }
  return 'info'
}

function getToneFill(tone: 'danger' | 'warning' | 'info'): string {
  if (tone === 'danger') return '#B91C1C'
  if (tone === 'warning') return '#B45309'
  return '#1D4ED8'
}

function getPanelFill(panelId: BodyPanel): string {
  if (props.selectedPanel === panelId) {
    return '#FFF4ED'
  }
  const defect = DEFECT_BY_PANEL.value.get(panelId)
  if (!defect) return '#F8F8FA'
  const tone = getPinTone(defect)
  if (tone === 'danger') return '#FEF2F2'
  if (tone === 'warning') return '#FFFBEB'
  return '#EFF6FF'
}

function getPanelStroke(panelId: BodyPanel): string {
  if (props.selectedPanel === panelId) {
    return '#FF6B00'
  }
  const defect = DEFECT_BY_PANEL.value.get(panelId)
  if (!defect) return '#D1D1D6'
  const tone = getPinTone(defect)
  if (tone === 'danger') return '#EF4444'
  if (tone === 'warning') return '#F59E0B'
  return '#3B82F6'
}

function togglePanel(panelId: BodyPanel): void {
  emit('update:selectedPanel', props.selectedPanel === panelId ? null : panelId)
}
</script>

<template>
  <div class="flex flex-col items-center gap-4">
    <svg
      viewBox="0 0 280 400"
      role="img"
      aria-label="Схема дефектов кузова автомобиля сверху"
      class="h-auto w-full max-w-[270px] select-none"
    >
      <!-- Outer Sills (left/right side skirts) -->
      <rect
        x="18"
        y="124"
        width="16"
        height="168"
        rx="6"
        :fill="getPanelFill('left_sill')"
        :stroke="getPanelStroke('left_sill')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('left_sill')"
      />
      <rect
        x="246"
        y="124"
        width="16"
        height="168"
        rx="6"
        :fill="getPanelFill('right_sill')"
        :stroke="getPanelStroke('right_sill')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('right_sill')"
      />

      <!-- Front Bumper -->
      <path
        d="M 64 46 C 64 26, 98 18, 140 18 C 182 18, 216 26, 216 46 L 210 58 L 70 58 Z"
        :fill="getPanelFill('front_bumper')"
        :stroke="getPanelStroke('front_bumper')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('front_bumper')"
      />

      <!-- Front Fenders -->
      <path
        d="M 42 56 L 70 58 L 72 126 L 38 126 L 38 72 C 38 62, 40 57, 42 56 Z"
        :fill="getPanelFill('front_left_fender')"
        :stroke="getPanelStroke('front_left_fender')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('front_left_fender')"
      />
      <path
        d="M 238 56 L 210 58 L 208 126 L 242 126 L 242 72 C 242 62, 240 57, 238 56 Z"
        :fill="getPanelFill('front_right_fender')"
        :stroke="getPanelStroke('front_right_fender')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('front_right_fender')"
      />

      <!-- Hood -->
      <path
        d="M 72 60 L 208 60 L 204 124 L 76 124 Z"
        :fill="getPanelFill('hood')"
        :stroke="getPanelStroke('hood')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('hood')"
      />

      <!-- Windshield -->
      <path
        d="M 76 126 L 204 126 L 194 164 L 86 164 Z"
        :fill="getPanelFill('windshield')"
        :stroke="getPanelStroke('windshield')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('windshield')"
      />

      <!-- Roof -->
      <rect
        x="86"
        y="166"
        width="108"
        height="108"
        rx="10"
        :fill="getPanelFill('roof')"
        :stroke="getPanelStroke('roof')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('roof')"
      />

      <!-- Front Doors -->
      <rect
        x="38"
        y="128"
        width="44"
        height="82"
        rx="4"
        :fill="getPanelFill('front_left_door')"
        :stroke="getPanelStroke('front_left_door')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('front_left_door')"
      />
      <rect
        x="198"
        y="128"
        width="44"
        height="82"
        rx="4"
        :fill="getPanelFill('front_right_door')"
        :stroke="getPanelStroke('front_right_door')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('front_right_door')"
      />

      <!-- Rear Doors -->
      <rect
        x="38"
        y="212"
        width="44"
        height="78"
        rx="4"
        :fill="getPanelFill('rear_left_door')"
        :stroke="getPanelStroke('rear_left_door')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('rear_left_door')"
      />
      <rect
        x="198"
        y="212"
        width="44"
        height="78"
        rx="4"
        :fill="getPanelFill('rear_right_door')"
        :stroke="getPanelStroke('rear_right_door')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('rear_right_door')"
      />

      <!-- Rear Quarters -->
      <path
        d="M 38 292 L 82 292 L 74 344 L 44 342 C 40 336, 38 324, 38 292 Z"
        :fill="getPanelFill('rear_left_quarter')"
        :stroke="getPanelStroke('rear_left_quarter')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('rear_left_quarter')"
      />
      <path
        d="M 198 292 L 242 292 C 242 324, 240 336, 236 342 L 206 344 Z"
        :fill="getPanelFill('rear_right_quarter')"
        :stroke="getPanelStroke('rear_right_quarter')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('rear_right_quarter')"
      />

      <!-- Tailgate / Trunk -->
      <path
        d="M 86 276 L 194 276 L 204 344 L 76 344 Z"
        :fill="getPanelFill('tailgate')"
        :stroke="getPanelStroke('tailgate')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('tailgate')"
      />

      <!-- Rear Bumper -->
      <path
        d="M 70 346 L 210 346 L 214 362 C 214 374, 180 382, 140 382 C 100 382, 66 374, 66 362 Z"
        :fill="getPanelFill('rear_bumper')"
        :stroke="getPanelStroke('rear_bumper')"
        stroke-width="1.5"
        class="cursor-pointer transition-colors"
        @click="togglePanel('rear_bumper')"
      />

      <!-- Subtle orientation labels -->
      <text
        x="140"
        y="12"
        text-anchor="middle"
        font-size="9"
        font-weight="600"
        fill="#9CA3AF"
        letter-spacing="0.08em"
      >
        ПЕРЕД
      </text>
      <text
        x="140"
        y="396"
        text-anchor="middle"
        font-size="9"
        font-weight="600"
        fill="#9CA3AF"
        letter-spacing="0.08em"
      >
        КОРМА
      </text>

      <!-- Defect Pins -->
      <g
        v-for="defect in uniquePinDefects"
        :key="defect.panel_id"
        role="button"
        tabindex="0"
        :aria-label="`${defect.panel_ru}: ${defect.raw_code}`"
        :aria-pressed="selectedPanel === defect.panel_id"
        class="focus:outline-accent cursor-pointer"
        @click="togglePanel(defect.panel_id)"
        @keydown.enter.prevent="togglePanel(defect.panel_id)"
        @keydown.space.prevent="togglePanel(defect.panel_id)"
      >
        <circle
          :cx="PANEL_COORDS[defect.panel_id].x"
          :cy="PANEL_COORDS[defect.panel_id].y"
          :r="selectedPanel === defect.panel_id ? 19 : 16"
          :fill="getToneFill(getPinTone(defect))"
          :stroke="selectedPanel === defect.panel_id ? '#FF6B00' : '#FFFFFF'"
          :stroke-width="selectedPanel === defect.panel_id ? 3 : 2"
        />
        <text
          :x="PANEL_COORDS[defect.panel_id].x"
          :y="PANEL_COORDS[defect.panel_id].y + 4"
          text-anchor="middle"
          font-size="10.5"
          font-weight="700"
          fill="#FFFFFF"
          style="font-family: ui-monospace, monospace"
        >
          {{ defect.raw_code.slice(0, 4) }}
        </text>
      </g>
    </svg>

    <div
      class="flex flex-wrap items-center justify-center gap-3 text-[11px] font-medium text-[#6B7280]"
    >
      <span class="inline-flex items-center gap-1.5">
        <span class="h-2.5 w-2.5 rounded-full bg-[#B91C1C]" />
        Замена / серьёзный дефект (XX, X, 3)
      </span>
      <span class="inline-flex items-center gap-1.5">
        <span class="h-2.5 w-2.5 rounded-full bg-[#B45309]" />
        Окрас / среднее (W, S, 2)
      </span>
      <span class="inline-flex items-center gap-1.5">
        <span class="h-2.5 w-2.5 rounded-full bg-[#1D4ED8]" />
        Косметика (A1, U1)
      </span>
    </div>
  </div>
</template>
