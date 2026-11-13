<script setup lang="ts">
import { computed } from 'vue'

import { formatRoiPercent, getBenefitBadgeVariant } from '@/components/lots/detail/lotPresentation'
import { BaseBadge, BaseCard } from '@/components/ui'
import { formatRub } from '@/utils/formatters'

interface Props {
  marketPriceRfRub: number
  turnkeyCostRub: number
  netBenefitRub: number
  benefitPercentage: number
}

const props = defineProps<Props>()

const badgeVariant = computed(() => getBenefitBadgeVariant(props.netBenefitRub))
const roiLabel = computed(() => `${formatRoiPercent(props.benefitPercentage)} ROI`)
</script>

<template>
  <BaseCard variant="surface" padding="md">
    <div class="mb-3 flex items-center justify-between gap-2">
      <h3 class="text-text-primary text-[15px] font-semibold">Сравнение с рынком РФ</h3>
      <BaseBadge :variant="badgeVariant">
        {{ roiLabel }}
      </BaseBadge>
    </div>

    <div class="flex flex-col gap-2 text-[14px]">
      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">1. Рыночная цена (Drom)</span>
        <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
          {{ formatRub(marketPriceRfRub) }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">2. Себестоимость под ключ</span>
        <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
          {{ formatRub(turnkeyCostRub) }}
        </span>
      </div>

      <div class="border-border mt-1 flex items-center justify-between gap-3 border-t pt-2.5">
        <span class="text-text-primary font-medium">3. Чистая выгода клиента</span>
        <span
          class="shrink-0 text-[17px] font-semibold whitespace-nowrap tabular-nums"
          :class="netBenefitRub >= 0 ? 'text-success' : 'text-danger'"
        >
          {{ formatRub(netBenefitRub, { signed: true }) }}
        </span>
      </div>
    </div>
  </BaseCard>
</template>
