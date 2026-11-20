<script setup lang="ts">
import { AlertTriangle, CheckCircle2, OctagonAlert } from '@lucide/vue'

import type { TrafficLightColor } from '@/types/api'

interface Props {
  verdict: TrafficLightColor
  bullets: readonly string[]
  density?: 'screen' | 'print'
}

withDefaults(defineProps<Props>(), {
  density: 'screen',
})
</script>

<template>
  <ul
    v-if="bullets.length > 0"
    :class="density === 'print' ? 'mt-2.5 flex flex-col gap-1' : 'mt-3 flex flex-col gap-1.5'"
  >
    <li
      v-for="(bullet, idx) in bullets"
      :key="`${idx}:${bullet}`"
      :class="
        density === 'print'
          ? 'flex items-start gap-1.5 text-[11.5px] leading-snug text-[#111827]'
          : 'text-text-primary flex items-start gap-2 text-[13px] leading-snug'
      "
    >
      <CheckCircle2
        v-if="verdict === 'green'"
        :size="density === 'print' ? 13 : 15"
        :class="
          density === 'print' ? 'mt-0.5 shrink-0 text-[#15803D]' : 'text-success mt-0.5 shrink-0'
        "
      />
      <AlertTriangle
        v-else-if="verdict === 'yellow'"
        :size="density === 'print' ? 13 : 15"
        :class="
          density === 'print' ? 'mt-0.5 shrink-0 text-[#B45309]' : 'text-warning mt-0.5 shrink-0'
        "
      />
      <OctagonAlert
        v-else
        :size="density === 'print' ? 13 : 15"
        :class="
          density === 'print' ? 'mt-0.5 shrink-0 text-[#B91C1C]' : 'text-danger mt-0.5 shrink-0'
        "
      />
      <span>{{ bullet }}</span>
    </li>
  </ul>
</template>
