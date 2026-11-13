<script setup lang="ts">
import { Pencil, RotateCcw } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import {
  BaseBadge,
  BaseButton,
  BaseCard,
  BaseSwitch,
  CostLadder,
  type CostLadderStep,
} from '@/components/ui'
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

const isEditingJpy = ref(false)
const jpyTextInput = ref('')
const jpyInputRef = ref<HTMLInputElement | null>(null)

const isEditingRub = ref(false)
const rubTextInput = ref('')
const rubInputRef = ref<HTMLInputElement | null>(null)

let sliderTimerId: number | null = null

function clearSliderTimer(): void {
  if (sliderTimerId !== null && typeof window !== 'undefined') {
    window.clearTimeout(sliderTimerId)
    sliderTimerId = null
  }
}

watch(
  () => ({
    lotId: props.detail.lot_id,
    bidJpy: props.detail.economics.wise_cost_ladder.car_bid_jpy,
    commercialUtil: props.detail.economics.customs.is_commercial_util,
    includeRepairs: props.detail.economics.is_repairs_included,
  }),
  (next) => {
    clearSliderTimer()
    draftBidJpy.value = next.bidJpy
    draftBidRubOverride.value = null
    draftCommercialUtil.value = next.commercialUtil
    draftIncludeRepairs.value = next.includeRepairs
    isEditingJpy.value = false
    isEditingRub.value = false
  },
)

onBeforeUnmount(() => {
  clearSliderTimer()
})

const sliderMinJpy = computed(() =>
  Math.min(props.detail.economics.bid_slider_min_jpy, draftBidJpy.value),
)
const sliderMaxJpy = computed(() =>
  Math.max(props.detail.economics.bid_slider_max_jpy, draftBidJpy.value),
)
const sliderStepJpy = computed(() => Math.max(1000, props.detail.economics.bid_slider_step_jpy))

const jpyRate = computed(() => props.detail.economics.customs.rates_snapshot.jpy_rub_bank || 0.64)

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

function formatJpy(amount: number): string {
  return `${Math.round(amount).toLocaleString('ru-RU')} ¥`
}

function parseNumericInput(raw: string): number | null {
  const digits = raw.replace(/[^\d]/g, '')
  if (!digits) return null
  const parsed = Number(digits)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function emitRecalculateNow(override?: { bidRub?: number }): void {
  clearSliderTimer()
  if (override?.bidRub !== undefined) {
    emit('recalculate', {
      bid_rub: override.bidRub,
      is_commercial_util: draftCommercialUtil.value,
      include_repairs: draftIncludeRepairs.value,
    })
    return
  }

  emit('recalculate', {
    bid_jpy: draftBidJpy.value,
    is_commercial_util: draftCommercialUtil.value,
    include_repairs: draftIncludeRepairs.value,
  })
}

function handleBidInput(event: Event): void {
  const target = event.target as HTMLInputElement
  draftBidRubOverride.value = null
  draftBidJpy.value = Number(target.value)
  clearSliderTimer()
  if (typeof window !== 'undefined') {
    sliderTimerId = window.setTimeout(() => {
      sliderTimerId = null
      emitRecalculateNow()
    }, SLIDER_DEBOUNCE_MS)
  }
}

function handleBidCommit(): void {
  if (sliderTimerId !== null || isLinearPreviewPending.value) {
    emitRecalculateNow()
  }
}

async function startEditingJpy(): Promise<void> {
  isEditingRub.value = false
  jpyTextInput.value = String(Math.round(draftBidJpy.value))
  isEditingJpy.value = true
  await nextTick()
  jpyInputRef.value?.focus()
  jpyInputRef.value?.select()
}

function cancelJpyEdit(): void {
  isEditingJpy.value = false
}

function commitJpyEdit(): void {
  if (!isEditingJpy.value) return
  isEditingJpy.value = false
  const parsed = parseNumericInput(jpyTextInput.value)
  if (parsed === null) return
  const clamped = Math.min(50_000_000, Math.max(100_000, Math.round(parsed)))
  draftBidRubOverride.value = null
  if (clamped === draftBidJpy.value) return
  draftBidJpy.value = clamped
  emitRecalculateNow()
}

async function startEditingRub(): Promise<void> {
  isEditingJpy.value = false
  rubTextInput.value = String(Math.round(displayBidRub.value))
  isEditingRub.value = true
  await nextTick()
  rubInputRef.value?.focus()
  rubInputRef.value?.select()
}

function cancelRubEdit(): void {
  isEditingRub.value = false
}

function commitRubEdit(): void {
  if (!isEditingRub.value) return
  isEditingRub.value = false
  const parsed = parseNumericInput(rubTextInput.value)
  if (parsed === null) return
  const clampedRub = Math.min(35_000_000, Math.max(50_000, Math.round(parsed)))
  if (clampedRub === displayBidRub.value) return
  draftBidRubOverride.value = clampedRub
  draftBidJpy.value = Math.max(100_000, Math.round(clampedRub / jpyRate.value))
  emitRecalculateNow({ bidRub: clampedRub })
}

function handleSwitchToggle(): void {
  emitRecalculateNow(
    draftBidRubOverride.value !== null ? { bidRub: draftBidRubOverride.value } : undefined,
  )
}

function handleReset(): void {
  clearSliderTimer()
  draftBidRubOverride.value = null
  isEditingJpy.value = false
  isEditingRub.value = false
  emit('resetSimulation')
}

function formatStepHint(
  stepNumber: number,
  currency: string | null,
  original: number | null,
): string | undefined {
  if (stepNumber === 1) {
    return `${formatJpy(draftBidJpy.value)} · курс ${jpyRate.value.toFixed(3)} ₽`
  }
  if (!currency || original === null) return undefined
  if (currency === 'EUR') {
    return `${original.toFixed(2)} EUR`
  }
  return `${Math.round(original).toLocaleString('ru-RU')} ${currency}`
}

const ladderSteps = computed<CostLadderStep[]>(() => {
  return props.detail.economics.wise_cost_ladder.steps.map((step) => {
    const amountRub = step.step_number === 1 ? displayBidRub.value : step.amount_rub
    return {
      label: step.name_ru,
      value: formatRub(amountRub),
      hint: formatStepHint(step.step_number, step.original_currency, step.original_amount),
      active:
        (step.step_number === 1 && isLinearPreviewPending.value) ||
        (step.step_number === 7 && draftIncludeRepairs.value && amountRub > 0),
    }
  })
})

const utilDescription = computed(() => {
  const isUnder160 = props.detail.economics.customs.is_under_160_hp
  if (draftCommercialUtil.value) {
    return 'Коммерческий тариф по ПП РФ № 1255 (для перепродажи / юрлица)'
  }
  if (isUnder160 === false) {
    return 'Мощность > 160 л.с. — применяется повышенный утильсбор'
  }
  return 'Льготный личный ввоз для физлица (≤ 160 л.с.): 5 200 ₽'
})
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:items-start lg:gap-5">
    <!-- Left Column: Interactive Simulator + Market Comparison -->
    <div class="flex min-w-0 flex-col gap-4 lg:col-span-5">
      <!-- Bid Simulator Card with Inline Editable JPY & RUB -->
      <BaseCard variant="surface" padding="md">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <span class="text-text-secondary text-[12px] font-medium">
              Максимальная ставка на аукционе
            </span>

            <!-- Inline Editable JPY -->
            <div class="mt-1">
              <div
                v-if="isEditingJpy"
                class="border-accent bg-surface ring-accent/15 inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 ring-2"
              >
                <input
                  ref="jpyInputRef"
                  v-model="jpyTextInput"
                  type="text"
                  inputmode="numeric"
                  aria-label="Введите ставку в иенах"
                  class="text-text-primary w-32 bg-transparent text-[22px] leading-tight font-semibold tabular-nums outline-none"
                  @keydown.enter.prevent="commitJpyEdit"
                  @keydown.escape.prevent="cancelJpyEdit"
                  @blur="commitJpyEdit"
                />
                <span class="text-text-secondary text-[18px] font-semibold">¥</span>
              </div>

              <button
                v-else
                type="button"
                aria-label="Изменить ставку в иенах"
                title="Нажмите, чтобы ввести точную ставку в иенах"
                class="group hover:bg-surface-inset focus-visible:outline-accent -mx-1.5 inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-0.5 transition-colors focus-visible:outline-2"
                @click="startEditingJpy"
              >
                <span
                  class="text-text-primary border-border group-hover:border-accent border-b border-dashed text-[24px] leading-tight font-semibold tabular-nums transition-colors"
                >
                  {{ formatJpy(draftBidJpy) }}
                </span>
                <Pencil
                  :size="14"
                  class="text-text-muted group-hover:text-accent shrink-0 transition-colors"
                />
              </button>
            </div>

            <!-- Inline Editable RUB -->
            <div class="mt-1">
              <div
                v-if="isEditingRub"
                class="border-accent bg-surface ring-accent/15 inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 ring-2"
              >
                <span class="text-text-secondary text-[13px]">≈</span>
                <input
                  ref="rubInputRef"
                  v-model="rubTextInput"
                  type="text"
                  inputmode="numeric"
                  aria-label="Введите ставку в рублях"
                  class="text-text-primary w-28 bg-transparent text-[14px] font-medium tabular-nums outline-none"
                  @keydown.enter.prevent="commitRubEdit"
                  @keydown.escape.prevent="cancelRubEdit"
                  @blur="commitRubEdit"
                />
                <span class="text-text-secondary text-[13px] font-medium">₽</span>
              </div>

              <button
                v-else
                type="button"
                aria-label="Изменить ставку в рублях"
                title="Нажмите, чтобы ввести бюджет ставки в рублях"
                class="group hover:bg-surface-inset focus-visible:outline-accent -mx-1.5 inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-0.5 transition-colors focus-visible:outline-2"
                @click="startEditingRub"
              >
                <span
                  class="text-text-secondary border-border group-hover:border-accent group-hover:text-text-primary border-b border-dashed text-[13px] tabular-nums transition-colors"
                >
                  ≈ {{ formatRub(displayBidRub) }}
                </span>
                <Pencil
                  :size="12"
                  class="text-text-muted group-hover:text-accent shrink-0 transition-colors"
                />
              </button>
            </div>
          </div>

          <BaseButton
            v-if="isSimulationModified || isLinearPreviewPending"
            variant="ghost"
            size="sm"
            pill
            @click="handleReset"
          >
            <template #icon-left>
              <RotateCcw :size="14" />
            </template>
            Сбросить
          </BaseButton>
        </div>

        <div class="mt-3">
          <input
            type="range"
            aria-label="Максимальная ставка на аукционе в иенах"
            :min="sliderMinJpy"
            :max="sliderMaxJpy"
            :step="sliderStepJpy"
            :value="draftBidJpy"
            class="accent-accent bg-surface-inset h-2 w-full cursor-pointer appearance-none rounded-full"
            @input="handleBidInput"
            @change="handleBidCommit"
          />

          <div
            class="text-text-muted mt-1 flex items-center justify-between text-[11px] tabular-nums"
          >
            <span>{{ formatJpy(sliderMinJpy) }}</span>
            <span>{{ formatJpy(sliderMaxJpy) }}</span>
          </div>
        </div>
      </BaseCard>

      <!-- Duty & Repair Switches -->
      <BaseCard variant="surface" padding="md">
        <div class="flex flex-col divide-y divide-[#E5E5EA]">
          <div class="pb-3">
            <BaseSwitch
              v-model="draftCommercialUtil"
              label="Коммерческий утильсбор"
              :description="utilDescription"
              @update:model-value="handleSwitchToggle"
            />
          </div>

          <div class="pt-3">
            <BaseSwitch
              v-model="draftIncludeRepairs"
              label="Включать смету ремонта Farpost"
              :description="`Учтёт ${formatRub(detail.economics.farpost_repair.grand_total_repair_rub)} на кузовные детали и работы`"
              @update:model-value="handleSwitchToggle"
            />
          </div>
        </div>
      </BaseCard>

      <!-- Market Comparison Card -->
      <BaseCard variant="surface" padding="md">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h3 class="text-text-primary text-[15px] font-semibold">Сравнение с рынком РФ</h3>
          <BaseBadge
            :variant="
              displayNetBenefitRub >= 150_000
                ? 'success'
                : displayNetBenefitRub >= 50_000
                  ? 'warning'
                  : 'danger'
            "
          >
            {{ displayBenefitPct > 0 ? '+' : '' }}{{ displayBenefitPct }}% ROI
          </BaseBadge>
        </div>

        <div class="flex flex-col gap-2 text-[14px]">
          <div class="flex items-center justify-between gap-3">
            <span class="text-text-secondary">1. Рыночная цена (Drom)</span>
            <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
              {{ formatRub(detail.market.market_price_rf_rub) }}
            </span>
          </div>

          <div class="flex items-center justify-between gap-3">
            <span class="text-text-secondary">2. Себестоимость под ключ</span>
            <span class="text-text-primary shrink-0 font-semibold whitespace-nowrap tabular-nums">
              {{ formatRub(displayTurnkeyRub) }}
            </span>
          </div>

          <div class="border-border mt-1 flex items-center justify-between gap-3 border-t pt-2.5">
            <span class="text-text-primary font-medium">3. Чистая выгода клиента</span>
            <span
              class="shrink-0 text-[17px] font-semibold whitespace-nowrap tabular-nums"
              :class="displayNetBenefitRub >= 0 ? 'text-success' : 'text-danger'"
            >
              {{ formatRub(displayNetBenefitRub, { signed: true }) }}
            </span>
          </div>
        </div>
      </BaseCard>
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
        <span class="text-text-primary font-medium">Курс валют: VL.ru Деньги</span>
      </div>
    </BaseCard>
  </div>
</template>
