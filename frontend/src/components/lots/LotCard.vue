<script setup lang="ts">
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  FileText,
  OctagonAlert,
  ShieldAlert,
} from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import { BaseBadge, BaseCard, type BadgeVariant } from '@/components/ui'
import type { LotSummary, TrafficLightColor } from '@/types/api'
import {
  cleanVerdictText,
  formatEngineLiters,
  formatMileageKm,
  formatRub,
  formatShortDateRu,
  formatVerdictLabelRu,
} from '@/utils/formatters'

interface Props {
  lot: LotSummary
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [lot: LotSummary]
}>()

const imageError = ref(false)

watch(
  () => props.lot.thumbnail_url,
  () => {
    imageError.value = false
  },
)

const VERDICT_BADGE_MAP: Record<
  TrafficLightColor,
  { variant: BadgeVariant; icon: typeof CheckCircle2 }
> = {
  green: { variant: 'success', icon: CheckCircle2 },
  yellow: { variant: 'warning', icon: AlertTriangle },
  red: { variant: 'danger', icon: OctagonAlert },
}

const verdictMeta = computed(() => VERDICT_BADGE_MAP[props.lot.verdict])
const verdictLabel = computed(() => formatVerdictLabelRu(props.lot.verdict))
const cleanedHeadline = computed(() => cleanVerdictText(props.lot.verdict_headline))
const hasThumbnail = computed(() => Boolean(props.lot.thumbnail_url) && !imageError.value)

const benefitClass = computed(() => {
  if (props.lot.net_benefit_rub > 0) return 'text-success'
  if (props.lot.net_benefit_rub < 0) return 'text-danger'
  return 'text-text-secondary'
})

const specsLine = computed(() => {
  const parts: string[] = []
  if (props.lot.year) parts.push(String(props.lot.year))
  if (props.lot.engine_cc) parts.push(formatEngineLiters(props.lot.engine_cc))
  if (props.lot.mileage_km !== null) parts.push(formatMileageKm(props.lot.mileage_km))
  parts.push(`${props.lot.auction_house} #${props.lot.lot_number}`)
  if (props.lot.overall_grade) parts.push(`Оценка ${props.lot.overall_grade}`)
  return parts.join(' · ')
})
</script>

<template>
  <BaseCard
    as="article"
    variant="surface"
    padding="none"
    interactive
    class="group h-full overflow-hidden"
  >
    <button
      type="button"
      class="flex h-full w-full cursor-pointer flex-col justify-between text-left outline-none focus:outline-none focus-visible:outline-none"
      @click="emit('select', lot)"
    >
      <div class="flex items-start gap-3.5 p-4 sm:gap-4 sm:p-4">
        <div
          class="bg-surface-inset border-border relative flex h-[94px] w-[68px] shrink-0 items-center justify-center overflow-hidden rounded-sm border"
        >
          <img
            v-if="hasThumbnail"
            :src="lot.thumbnail_url!"
            :alt="`Аукционный лист ${lot.make} ${lot.model} #${lot.lot_number}`"
            class="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
            loading="lazy"
            @error="imageError = true"
          />
          <div
            v-else
            class="text-text-tertiary flex flex-col items-center gap-1 px-1.5 text-center"
          >
            <FileText :size="18" :stroke-width="1.6" />
            <span class="text-[10px] leading-tight font-medium">Скан листа</span>
          </div>
        </div>

        <div class="flex min-w-0 flex-1 flex-col gap-2">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <h3
                class="text-text-primary group-hover:text-accent truncate text-[16px] leading-snug font-semibold transition-colors"
              >
                {{ lot.make }} {{ lot.model }}
              </h3>
              <p class="text-text-secondary mt-0.5 truncate text-[12px] leading-snug">
                {{ specsLine }}
              </p>
            </div>

            <ChevronRight
              :size="18"
              class="text-text-tertiary group-hover:text-accent mt-0.5 shrink-0 transition-transform duration-150 group-hover:translate-x-0.5"
            />
          </div>

          <div class="flex flex-wrap items-center gap-1.5">
            <BaseBadge :variant="verdictMeta.variant" size="sm">
              <template #icon>
                <component :is="verdictMeta.icon" :size="12" :stroke-width="2" />
              </template>
              {{ verdictLabel }}
            </BaseBadge>

            <BaseBadge v-if="lot.meti_sanction_risk" variant="warning" size="sm">
              <template #icon>
                <ShieldAlert :size="12" :stroke-width="2" />
              </template>
              METI риск
            </BaseBadge>

            <span
              class="bg-surface-inset text-text-secondary inline-flex min-h-5 items-center rounded-full px-2 py-0.5 font-mono text-[11px] font-medium"
            >
              {{ lot.frame_id }}
            </span>
          </div>

          <div
            class="border-border flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-t pt-2"
          >
            <div>
              <div class="text-text-primary text-[17px] leading-tight font-semibold">
                {{ formatRub(lot.turnkey_cost_rub) }}
              </div>
              <div class="text-text-tertiary mt-0.5 text-[11px] leading-tight">
                под ключ · РФ ~{{ formatRub(lot.market_price_rf_rub) }}
              </div>
            </div>

            <div class="text-right">
              <div class="text-[14px] leading-tight font-semibold" :class="benefitClass">
                {{ formatRub(lot.net_benefit_rub, { signed: true }) }}
              </div>
              <div class="text-text-tertiary mt-0.5 text-[11px] leading-tight">
                {{ formatShortDateRu(lot.created_at) }}
              </div>
            </div>
          </div>

          <p
            v-if="cleanedHeadline && !lot.has_anomaly"
            class="text-text-secondary line-clamp-1 text-[12px] leading-snug"
          >
            {{ cleanedHeadline }}
          </p>
        </div>
      </div>

      <div
        v-if="lot.has_anomaly && lot.anomaly_text"
        class="bg-danger-bg text-danger border-danger/10 flex items-start gap-2 border-t px-4 py-2 text-[12px] leading-snug"
      >
        <AlertTriangle :size="14" :stroke-width="2" class="mt-0.5 shrink-0" />
        <span class="line-clamp-2 font-medium">{{ lot.anomaly_text }}</span>
      </div>
    </button>
  </BaseCard>
</template>
