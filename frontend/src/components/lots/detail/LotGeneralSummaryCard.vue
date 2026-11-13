<script setup lang="ts">
import { SlidersHorizontal } from '@lucide/vue'
import { computed } from 'vue'

import { BaseBadge, BaseCard } from '@/components/ui'
import type { LotDetailResponse, TrafficLightColor } from '@/types/api'
import { formatRub } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  openEconomicsTab: []
}>()

const BADGE_VARIANTS: Record<TrafficLightColor, 'success' | 'warning' | 'danger'> = {
  green: 'success',
  yellow: 'warning',
  red: 'danger',
}

const badgeVariant = computed(() => BADGE_VARIANTS[props.detail.verdict.verdict])
const turnkeyCostRub = computed(() => props.detail.economics.wise_cost_ladder.turnkey_cost_rub)
</script>

<template>
  <BaseCard variant="surface" padding="lg">
    <div class="flex items-start justify-between gap-3">
      <div>
        <div class="text-text-secondary text-[13px] font-medium">Себестоимость под ключ</div>
        <div
          class="text-text-primary mt-1 text-[30px] leading-tight font-semibold tracking-[-0.02em] tabular-nums"
        >
          {{ formatRub(turnkeyCostRub) }}
        </div>
      </div>

      <BaseBadge :variant="badgeVariant">
        {{ detail.verdict.badge_text }}
      </BaseBadge>
    </div>

    <div class="border-border mt-4 flex flex-col gap-2 border-t pt-3.5 text-[14px]">
      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary"
          >Рынок РФ (Drom · {{ detail.market.analogs_count }} авто)</span
        >
        <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
          {{ formatRub(detail.market.market_price_rf_rub) }}
        </span>
      </div>

      <div
        v-if="detail.market.price_min_rub && detail.market.price_max_rub"
        class="flex items-center justify-between gap-3 text-[13px]"
      >
        <span class="text-text-secondary min-w-0"
          >Разброс в наличии ({{ detail.market.search_region_ru }})</span
        >
        <span class="text-text-secondary shrink-0 whitespace-nowrap tabular-nums">
          {{ formatRub(detail.market.price_min_rub) }} –
          {{ formatRub(detail.market.price_max_rub) }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">Ремонт в смете Farpost</span>
        <span class="text-text-primary shrink-0 font-medium whitespace-nowrap tabular-nums">
          {{
            detail.economics.is_repairs_included
              ? formatRub(detail.economics.farpost_repair.grand_total_repair_rub)
              : 'Исключён (0 ₽)'
          }}
        </span>
      </div>

      <div class="flex items-center justify-between gap-3">
        <span class="text-text-secondary">Доходность (ROI)</span>
        <span
          class="shrink-0 font-semibold whitespace-nowrap tabular-nums"
          :class="detail.verdict.net_benefit_rub >= 0 ? 'text-success' : 'text-danger'"
        >
          {{ detail.verdict.benefit_percentage > 0 ? '+' : ''
          }}{{ detail.verdict.benefit_percentage }}%
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
