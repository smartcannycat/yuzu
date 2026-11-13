<script setup lang="ts">
import { BaseBadge, BaseCard } from '@/components/ui'
import { formatRub } from '@/utils/formatters'

interface Props {
  marketPriceRfRub: number
  turnkeyCostRub: number
  netBenefitRub: number
  benefitPercentage: number
}

defineProps<Props>()
</script>

<template>
  <BaseCard variant="surface" padding="md">
    <div class="mb-3 flex items-center justify-between gap-2">
      <h3 class="text-text-primary text-[15px] font-semibold">Сравнение с рынком РФ</h3>
      <BaseBadge
        :variant="
          netBenefitRub >= 150_000 ? 'success' : netBenefitRub >= 50_000 ? 'warning' : 'danger'
        "
      >
        {{ benefitPercentage > 0 ? '+' : '' }}{{ benefitPercentage }}% ROI
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
