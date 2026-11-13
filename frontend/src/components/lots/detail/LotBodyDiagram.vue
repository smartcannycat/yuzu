<script setup lang="ts">
import { computed } from 'vue'

import {
  BODY_PANEL_PIN_COORDS,
  BODY_PANEL_SHAPES,
  getDefectTone,
  getTonePanelColors,
  getTonePinFill,
} from '@/components/lots/detail/lotDefects'
import type { BodyPanel, NormalizedDefect } from '@/types/api'

interface Props {
  defects: NormalizedDefect[]
  selectedPanel: BodyPanel | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:selectedPanel': [panel: BodyPanel | null]
}>()

const defectByPanel = computed(() => {
  const map = new Map<BodyPanel, NormalizedDefect>()
  for (const defect of props.defects) {
    if (!map.has(defect.panel_id)) {
      map.set(defect.panel_id, defect)
    }
  }
  return map
})

const uniquePinDefects = computed(() => Array.from(defectByPanel.value.values()))

function getPanelColors(panelId: BodyPanel) {
  const defect = defectByPanel.value.get(panelId)
  const tone = defect ? getDefectTone(defect) : null
  return getTonePanelColors(tone, props.selectedPanel === panelId)
}

function togglePanel(panelId: BodyPanel): void {
  emit('update:selectedPanel', props.selectedPanel === panelId ? null : panelId)
}
</script>

<template>
  <div class="flex flex-col items-center gap-3">
    <svg
      viewBox="0 0 280 400"
      role="img"
      aria-label="Схема дефектов кузова автомобиля сверху"
      class="h-auto w-full max-w-[232px] select-none sm:max-w-[244px]"
    >
      <template v-for="shape in BODY_PANEL_SHAPES" :key="shape.id">
        <rect
          v-if="shape.kind === 'rect'"
          :x="shape.x"
          :y="shape.y"
          :width="shape.width"
          :height="shape.height"
          :rx="shape.rx"
          :fill="getPanelColors(shape.id).fill"
          :stroke="getPanelColors(shape.id).stroke"
          stroke-width="1.5"
          class="cursor-pointer transition-colors"
          @click="togglePanel(shape.id)"
        />
        <path
          v-else
          :d="shape.d"
          :fill="getPanelColors(shape.id).fill"
          :stroke="getPanelColors(shape.id).stroke"
          stroke-width="1.5"
          class="cursor-pointer transition-colors"
          @click="togglePanel(shape.id)"
        />
      </template>

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
          :cx="BODY_PANEL_PIN_COORDS[defect.panel_id].x"
          :cy="BODY_PANEL_PIN_COORDS[defect.panel_id].y"
          :r="selectedPanel === defect.panel_id ? 19 : 16"
          :fill="getTonePinFill(getDefectTone(defect))"
          :stroke="selectedPanel === defect.panel_id ? '#FF6B00' : '#FFFFFF'"
          :stroke-width="selectedPanel === defect.panel_id ? 3 : 2"
        />
        <text
          :x="BODY_PANEL_PIN_COORDS[defect.panel_id].x"
          :y="BODY_PANEL_PIN_COORDS[defect.panel_id].y + 3.5"
          text-anchor="middle"
          :font-size="defect.raw_code.length > 3 ? 9 : 10.5"
          font-weight="700"
          fill="#FFFFFF"
          style="font-family: ui-monospace, monospace"
        >
          {{ defect.raw_code.slice(0, 5) }}
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
