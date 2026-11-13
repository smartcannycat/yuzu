<script setup lang="ts">
import { computed } from 'vue'

import { BaseBadge, BaseButton, BottomSheet, InsetListGroup, InsetListItem } from '@/components/ui'
import type { LotSummary } from '@/types/api'
import { formatMileageKm, formatRub, formatVerdictLabelRu } from '@/utils/formatters'

const lot = defineModel<LotSummary | null>('lot', { default: null })

const isLotOpen = computed({
  get: () => lot.value !== null,
  set: (value: boolean) => {
    if (!value) lot.value = null
  },
})
</script>

<template>
  <BottomSheet
    v-model:open="isLotOpen"
    :title="lot ? `${lot.make} ${lot.model}` : 'Карточка лота'"
    :subtitle="lot ? `${lot.auction_house} #${lot.lot_number} · ${lot.frame_id}` : undefined"
    max-width="md"
  >
    <div v-if="lot" class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-2">
        <BaseBadge
          :variant="
            lot.verdict === 'green' ? 'success' : lot.verdict === 'yellow' ? 'warning' : 'danger'
          "
        >
          {{ formatVerdictLabelRu(lot.verdict) }}
        </BaseBadge>
        <BaseBadge v-if="lot.meti_sanction_risk" variant="warning">
          METI санкционный риск
        </BaseBadge>
      </div>

      <InsetListGroup>
        <InsetListItem
          title="Цена под ключ"
          :value="formatRub(lot.turnkey_cost_rub)"
          squircle-color="#FF6B00"
        />
        <InsetListItem
          title="Рынок РФ (Drom)"
          :value="formatRub(lot.market_price_rf_rub)"
          squircle-color="#1D4ED8"
        />
        <InsetListItem
          title="Выгода"
          :value="formatRub(lot.net_benefit_rub, { signed: true })"
          squircle-color="#15803D"
        />
        <InsetListItem
          title="Пробег и оценка"
          :value="`${formatMileageKm(lot.mileage_km)} · ${lot.overall_grade}`"
          squircle-color="#6B7280"
        />
      </InsetListGroup>

      <p class="text-text-secondary text-[13px] leading-relaxed">
        Полная детализация с интерактивным пересчётом ставки, раскладкой пошлин и картой дефектов
        будет доступна на Экране 4 (FE-06).
      </p>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="lot = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
