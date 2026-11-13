<script setup lang="ts">
import { computed } from 'vue'

import LotPrintPageGeneral from '@/components/lots/detail/print/LotPrintPageGeneral.vue'
import LotPrintPageTechEconomics from '@/components/lots/detail/print/LotPrintPageTechEconomics.vue'
import type { LotDetailResponse } from '@/types/api'

interface Props {
  detail: LotDetailResponse
  isSimulationModified?: boolean
}

withDefaults(defineProps<Props>(), {
  isSimulationModified: false,
})

const reportDateLabel = computed(() =>
  new Date().toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }),
)
</script>

<template>
  <article class="hidden bg-white px-[12mm] text-[#111827] print:block">
    <LotPrintPageGeneral
      :detail="detail"
      :is-simulation-modified="isSimulationModified"
      :report-date-label="reportDateLabel"
    />
    <LotPrintPageTechEconomics :detail="detail" />
  </article>
</template>
