<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import LotBidSimulatorCard from '@/components/lots/detail/LotBidSimulatorCard.vue'
import LotEconomicsSwitchesCard from '@/components/lots/detail/LotEconomicsSwitchesCard.vue'
import LotMarketComparisonCard from '@/components/lots/detail/LotMarketComparisonCard.vue'
import {
  FX_RATE_SOURCE_LABEL,
  buildCostLadderSteps,
  clampBidJpy,
  clampBidRub,
  formatUtilModeLabel,
  parsePositiveIntegerInput,
  resolveSafeJpyRate,
} from '@/components/lots/detail/lotPresentation'
import { BaseBadge, BaseCard, CostLadder } from '@/components/ui'
import type { LotDetailResponse, RecalculateRequest } from '@/types/api'
import { formatRub } from '@/utils/formatters'

interface Props {
  detail: LotDetailResponse
  isRecalculating?: boolean
  recalculateError?: string | null
  isSimulationModified?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isRecalculating: false,
  recalculateError: null,
  isSimulationModified: false,
})

const emit = defineEmits<{
  recalculate: [payload: RecalculateRequest]
  resetSimulation: []
}>()

const SLIDER_DEBOUNCE_MS = 300

const draftBidJpy = ref(props.detail.economics.wise_cost_ladder.car_bid_jpy)
const draftBidRubOverride = ref<number | null>(null)
const draftCommercialUtil = ref(props.detail.economics.customs.is_commercial_util)
const draftIncludeRepairs = ref(props.detail.economics.is_repairs_included)
const draftPowerHpInput = ref(
  props.detail.passport.power_hp !== null ? String(props.detail.passport.power_hp) : '',
)

let sliderTimerId: number | null = null

function clearSliderTimer(): void {
  if (sliderTimerId !== null && typeof window !== 'undefined') {
    window.clearTimeout(sliderTimerId)
    sliderTimerId = null
  }
}

function resetDraftsFromProps(): void {
  clearSliderTimer()
  draftBidJpy.value = props.detail.economics.wise_cost_ladder.car_bid_jpy
  draftBidRubOverride.value = null
  draftCommercialUtil.value = props.detail.economics.customs.is_commercial_util
  draftIncludeRepairs.value = props.detail.economics.is_repairs_included
  draftPowerHpInput.value =
    props.detail.passport.power_hp !== null ? String(props.detail.passport.power_hp) : ''
}

watch(
  [
    () => props.detail.lot_id,
    () => props.detail.economics.wise_cost_ladder.car_bid_jpy,
    () => props.detail.economics.customs.is_commercial_util,
    () => props.detail.economics.is_repairs_included,
    () => props.detail.passport.power_hp,
  ],
  () => {
    resetDraftsFromProps()
  },
)

watch(
  () => props.recalculateError,
  (nextError) => {
    if (nextError) {
      resetDraftsFromProps()
    }
  },
)

onBeforeUnmount(() => {
  clearSliderTimer()
})

const jpyRate = computed(() =>
  resolveSafeJpyRate(props.detail.economics.customs.rates_snapshot.jpy_rub_bank),
)

const isLinearPreviewPending = computed(
  () =>
    draftBidRubOverride.value !== null ||
    draftBidJpy.value !== props.detail.economics.wise_cost_ladder.car_bid_jpy,
)

const displayBidRub = computed(() => {
  if (draftBidRubOverride.value !== null) {
    return draftBidRubOverride.value
  }
  if (!isLinearPreviewPending.value) {
    return props.detail.economics.wise_cost_ladder.car_bid_rub
  }
  return Math.round(draftBidJpy.value * jpyRate.value)
})

const bidDeltaRub = computed(
  () => displayBidRub.value - props.detail.economics.wise_cost_ladder.car_bid_rub,
)

const displayTurnkeyRub = computed(() =>
  Math.max(0, props.detail.economics.wise_cost_ladder.turnkey_cost_rub + bidDeltaRub.value),
)

const displayNetBenefitRub = computed(
  () => props.detail.market.market_price_rf_rub - displayTurnkeyRub.value,
)

const displayBenefitPct = computed(() => {
  if (displayTurnkeyRub.value <= 0) return 0
  return Number(((displayNetBenefitRub.value / displayTurnkeyRub.value) * 100).toFixed(1))
})

function emitRecalculateNow(override?: { bidRub?: number; customPowerHp?: number }): void {
  clearSliderTimer()
  const basePayload: RecalculateRequest = {
    is_commercial_util: draftCommercialUtil.value,
    include_repairs: draftIncludeRepairs.value,
    ...(override?.customPowerHp !== undefined ? { custom_power_hp: override.customPowerHp } : {}),
  }
  if (override?.bidRub !== undefined) {
    emit('recalculate', {
      ...basePayload,
      bid_rub: override.bidRub,
    })
    return
  }

  emit('recalculate', {
    ...basePayload,
    bid_jpy: draftBidJpy.value,
  })
}

function handleSliderInput(nextBidJpy: number): void {
  draftBidRubOverride.value = null
  draftBidJpy.value = nextBidJpy
  clearSliderTimer()
  if (typeof window !== 'undefined') {
    sliderTimerId = window.setTimeout(() => {
      sliderTimerId = null
      emitRecalculateNow()
    }, SLIDER_DEBOUNCE_MS)
  }
}

function handleSliderCommit(): void {
  if (sliderTimerId !== null || isLinearPreviewPending.value) {
    emitRecalculateNow()
  }
}

function handleCommitJpy(nextBidJpy: number): void {
  const safeJpy = clampBidJpy(nextBidJpy)
  draftBidRubOverride.value = null
  draftBidJpy.value = safeJpy
  emitRecalculateNow()
}

function handleCommitRub(nextBidRub: number): void {
  const safeRub = clampBidRub(nextBidRub, jpyRate.value)
  draftBidRubOverride.value = safeRub
  draftBidJpy.value = clampBidJpy(Math.round(safeRub / jpyRate.value))
  emitRecalculateNow({ bidRub: safeRub })
}

function handleApplyCustomPower(): void {
  const parsed = parsePositiveIntegerInput(draftPowerHpInput.value)
  if (parsed === null || parsed < 1 || parsed > 2000) return
  draftPowerHpInput.value = String(parsed)
  emitRecalculateNow({
    ...(draftBidRubOverride.value !== null ? { bidRub: draftBidRubOverride.value } : {}),
    customPowerHp: parsed,
  })
}

function handleSwitchToggle(): void {
  emitRecalculateNow(
    draftBidRubOverride.value !== null ? { bidRub: draftBidRubOverride.value } : undefined,
  )
}

function handleReset(): void {
  clearSliderTimer()
  draftBidRubOverride.value = null
  emit('resetSimulation')
}

const ladderSteps = computed(() =>
  buildCostLadderSteps(props.detail.economics.wise_cost_ladder.steps, {
    bidJpy: draftBidJpy.value,
    jpyRate: jpyRate.value,
    displayBidRub: displayBidRub.value,
    isPreviewPending: isLinearPreviewPending.value,
    includeRepairs: draftIncludeRepairs.value,
  }),
)

const utilDescription = computed(() =>
  formatUtilModeLabel(
    draftCommercialUtil.value,
    props.detail.economics.customs.is_under_160_hp,
    'detailed',
    props.detail.economics.customs.utilization_fee_rub,
  ),
)

const isUtilModeForcedCommercial = computed(
  () => props.detail.economics.customs.is_under_160_hp !== true,
)
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:items-start lg:gap-5">
    <!-- Left Column: Interactive Simulator + Switches + Market Comparison -->
    <div class="flex min-w-0 flex-col gap-4 lg:col-span-5">
      <LotBidSimulatorCard
        :bid-jpy="draftBidJpy"
        :display-bid-rub="displayBidRub"
        :jpy-rate="jpyRate"
        :min-jpy="detail.economics.bid_slider_min_jpy"
        :max-jpy="detail.economics.bid_slider_max_jpy"
        :step-jpy="Math.max(1000, detail.economics.bid_slider_step_jpy)"
        :show-reset="isSimulationModified || isLinearPreviewPending"
        :is-recalculating="isRecalculating"
        @slider-input="handleSliderInput"
        @slider-commit="handleSliderCommit"
        @commit-jpy="handleCommitJpy"
        @commit-rub="handleCommitRub"
        @reset="handleReset"
      />

      <LotEconomicsSwitchesCard
        v-model:commercial-util="draftCommercialUtil"
        v-model:include-repairs="draftIncludeRepairs"
        v-model:power-hp-input="draftPowerHpInput"
        :util-description="utilDescription"
        :is-util-mode-forced-commercial="isUtilModeForcedCommercial"
        :repair-total-rub="detail.economics.farpost_repair.grand_total_repair_rub"
        :power-hp="detail.passport.power_hp"
        :is-recalculating="isRecalculating"
        @toggle-switch="handleSwitchToggle"
        @apply-power="handleApplyCustomPower"
      />

      <LotMarketComparisonCard
        :market-price-rf-rub="detail.market.market_price_rf_rub"
        :turnkey-cost-rub="displayTurnkeyRub"
        :net-benefit-rub="displayNetBenefitRub"
        :benefit-percentage="displayBenefitPct"
      />
    </div>

    <!-- Right Column: Turnkey Cost Calculator -->
    <BaseCard variant="surface" padding="lg" class="min-w-0 lg:col-span-7">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="text-text-primary text-[16px] font-semibold">
            Себестоимость привоза во Владивосток под ключ
          </h2>
          <p class="text-text-secondary text-[12px]">
            Пошаговый расчёт от аукционной ставки до выдачи ЭПТС
          </p>
        </div>

        <BaseBadge v-if="isRecalculating" variant="info">Пересчёт...</BaseBadge>
      </div>

      <p
        v-if="recalculateError"
        role="alert"
        class="bg-danger-bg text-danger mb-3 rounded-sm px-3 py-2 text-[13px]"
      >
        {{ recalculateError }}
      </p>

      <CostLadder
        :steps="ladderSteps"
        total-label="Итого под ключ во Владивостоке"
        :total-value="formatRub(displayTurnkeyRub)"
      />

      <div
        class="text-text-secondary border-border mt-4 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-[12px]"
      >
        <span>
          Курсы на {{ detail.economics.customs.rates_snapshot.cbrf_date }}: 1 ¥ =
          {{ jpyRate.toFixed(3) }} ₽ · 1 € =
          {{ detail.economics.customs.rates_snapshot.eur_rub_cbrf.toFixed(2) }} ₽
        </span>
        <span class="text-text-primary font-medium">Курс валют: {{ FX_RATE_SOURCE_LABEL }}</span>
      </div>
    </BaseCard>
  </div>
</template>
