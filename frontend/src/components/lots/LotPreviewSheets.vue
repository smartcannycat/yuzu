<script setup lang="ts">
import { computed } from 'vue'

import { CapyMascot } from '@/components/mascot'
import { BaseBadge, BaseButton, BottomSheet, InsetListGroup, InsetListItem } from '@/components/ui'
import type { InProgressItemPreview, LotSummary } from '@/types/api'
import {
  formatMileageKm,
  formatRub,
  formatTaskStepRu,
  formatVerdictLabelRu,
} from '@/utils/formatters'

const uploadOpen = defineModel<boolean>('uploadOpen', { default: false })
const lot = defineModel<LotSummary | null>('lot', { default: null })
const processingItem = defineModel<InProgressItemPreview | null>('processingItem', {
  default: null,
})

const isLotOpen = computed({
  get: () => lot.value !== null,
  set: (value: boolean) => {
    if (!value) lot.value = null
  },
})

const isProcessingOpen = computed({
  get: () => processingItem.value !== null,
  set: (value: boolean) => {
    if (!value) processingItem.value = null
  },
})
</script>

<template>
  <BottomSheet
    v-model:open="uploadOpen"
    title="Загрузка аукционных листов"
    subtitle="Экран 2 (FE-04) — следующий этап разработки"
    max-width="sm"
  >
    <div class="flex flex-col items-center gap-4 text-center">
      <CapyMascot state="peeking" size="compact" hide-badge />
      <p class="text-text-secondary text-[14px] leading-relaxed">
        Здесь откроется пакетная загрузка 1–10 фото или сканов аукционных листов с расчётом таможни
        и проверкой санкций METI.
      </p>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="uploadOpen = false">Понятно</BaseButton>
    </template>
  </BottomSheet>

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

  <BottomSheet
    v-model:open="isProcessingOpen"
    :title="processingItem?.display_title || 'Статус обработки'"
    subtitle="Экран 3 (FE-05) — следующий этап разработки"
    max-width="sm"
  >
    <div v-if="processingItem" class="flex flex-col gap-3">
      <InsetListGroup>
        <InsetListItem
          title="Текущий шаг"
          :value="formatTaskStepRu(processingItem.current_step)"
          squircle-color="#1D4ED8"
        />
      </InsetListGroup>
      <p class="text-text-secondary text-[13px] leading-relaxed">
        Отдельный экран мониторинга батча и живого переключения шагов будет реализован в задаче
        FE-05.
      </p>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="processingItem = null">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
