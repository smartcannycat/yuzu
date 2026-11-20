<script setup lang="ts">
import { SlidersHorizontal } from '@lucide/vue'
import { computed } from 'vue'

import { VERDICT_META } from '@/components/lots/detail/lotPresentation'
import { buildLotFinancialSummary } from '@/components/lots/detail/lotSummaryHelpers'
import { BaseBadge, BaseCard } from '@/components/ui'
import type { LotDetailResponse } from '@/types/api'

interface Props {
  detail: LotDetailResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  openEconomicsTab: []
}>()

const badgeVariant = computed(() => VERDICT_META[props.detail.verdict.verdict].badgeVariant)
const summary = computed(() => buildLotFinancialSummary(props.detail))
</script>

<template>
  <BaseCard variant="surface" padding="lg">
    <div class="flex flex-wrap items-start justify-between gap-2.5">
      <div class="min-w-0">
        <div class="text-text-secondary text-[13px] font-medium">Себестоимость под ключ</div>
        <div
          class="text-text-primary mt-1 text-[30px] leading-tight font-semibold tracking-[-0.02em] whitespace-nowrap tabular-nums"
        >
          {{ summary.turnkeyFormatted }}
        </div>
      </div>

      <BaseBadge :variant="badgeVariant" wrap>
        {{ detail.verdict.badge_text }}
      </BaseBadge>
    </div>

    <div class="border-border mt-4 flex flex-col gap-2 border-t pt-3.5 text-[14px]">
      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">{{ summary.marketLabel }}</span>
        <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
          {{ summary.marketPriceFormatted }}
        </span>
      </div>

      <div v-if="summary.dromRangeText" class="flex items-center justify-between gap-3 text-[13px]">
        <span class="text-text-secondary min-w-0">{{ summary.dromRangeLabel }}</span>
        <span class="text-text-secondary shrink-0 whitespace-nowrap tabular-nums">
          {{ summary.dromRangeText }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">Ремонт в смете Farpost</span>
        <span class="text-text-primary shrink-0 font-medium whitespace-nowrap tabular-nums">
          {{ summary.repairFormatted }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">Доходность (ROI)</span>
        <span
          class="shrink-0 font-semibold whitespace-nowrap tabular-nums"
          :class="detail.verdict.net_benefit_rub >= 0 ? 'text-success' : 'text-danger'"
        >
          {{ summary.roiFormatted }}
        </span>
      </div>
    </div>

    <button
      type="button"
      class="bg-surface-inset hover:bg-surface-hover text-text-primary mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-sm px-3.5 py-2.5 text-[13px] font-medium transition-colors"
      @click="emit('openEconomicsTab')"
    >
      <SlidersHorizontal :size="15" :stroke-width="1.9" />
      <span>Настроить ставку и утильсбор</span>
    </button>
  </BaseCard>
</template>
