<script setup lang="ts">
import { BaseBadge, BaseButton, BottomSheet } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'
import { formatRub } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
}

defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })
</script>

<template>
  <BottomSheet
    v-model:open="open"
    title="Смета ремонта Farpost"
    :subtitle="`Итого: ${formatRub(detail.economics.farpost_repair.grand_total_repair_rub)}`"
    max-width="md"
  >
    <div class="flex flex-col gap-4">
      <div v-if="detail.economics.farpost_repair.parts.length > 0" class="flex flex-col gap-2">
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Кузовные и контрактные детали
        </h4>
        <div
          v-for="part in detail.economics.farpost_repair.parts"
          :key="`${part.panel_id}-${part.defect_code}`"
          class="border-border bg-surface rounded-sm border p-3"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-text-primary text-[14px] font-medium">{{ part.part_name_ru }}</div>
              <p v-if="part.subtitle_ru" class="text-text-secondary mt-0.5 text-[12px]">
                {{ part.subtitle_ru }}
              </p>
            </div>
            <span class="text-text-primary shrink-0 text-[14px] font-semibold tabular-nums">
              от {{ formatRub(part.price_from_rub) }}
            </span>
          </div>

          <div class="mt-2 flex flex-wrap gap-1.5">
            <BaseBadge :variant="part.in_stock_vladivostok ? 'success' : 'warning'">
              {{
                part.in_stock_vladivostok ? 'В наличии во Владивостоке' : 'Под подбор / статистика'
              }}
            </BaseBadge>
            <BaseBadge variant="neutral">Код {{ part.defect_code }}</BaseBadge>
          </div>
        </div>
      </div>

      <div
        v-if="detail.economics.farpost_repair.service_works.length > 0"
        class="flex flex-col gap-2"
      >
        <h4 class="text-text-secondary text-[12px] font-semibold tracking-[0.04em] uppercase">
          Работы СТО и покраска
        </h4>
        <div
          v-for="work in detail.economics.farpost_repair.service_works"
          :key="work.label_ru"
          class="border-border bg-surface-inset/50 flex items-start justify-between gap-3 rounded-sm border p-3"
        >
          <div class="min-w-0">
            <div class="text-text-primary text-[13px] font-medium">{{ work.label_ru }}</div>
            <div v-if="work.zero_cost_reason_ru" class="text-success mt-0.5 text-[12px]">
              {{ work.zero_cost_reason_ru }}
            </div>
          </div>
          <span class="text-text-primary shrink-0 text-[14px] font-semibold tabular-nums">
            {{ formatRub(work.amount_rub) }}
          </span>
        </div>
      </div>

      <div
        v-if="
          detail.economics.farpost_repair.parts.length === 0 &&
          detail.economics.farpost_repair.service_works.length === 0
        "
        class="bg-success-bg text-success rounded-sm p-3.5 text-[13px]"
      >
        Существенных кузовных повреждений под ремонт не выявлено.
      </div>

      <div class="bg-surface-inset text-text-secondary rounded-sm px-3.5 py-2.5 text-[12px]">
        {{ detail.economics.farpost_repair.included_in_turnkey_hint_ru }}
      </div>
    </div>

    <template #footer>
      <BaseButton variant="primary" block @click="open = false">Закрыть</BaseButton>
    </template>
  </BottomSheet>
</template>
