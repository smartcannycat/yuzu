<script setup lang="ts">
import { CheckCircle2, ChevronRight, Clock, Loader2, OctagonAlert, Trash2 } from '@lucide/vue'
import { computed } from 'vue'

import { BaseBadge, BaseCard } from '@/components/ui'
import type { BatchItemStatus } from '@/types/api'
import { formatRub, formatTaskStepRu } from '@/utils/formatters'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'

interface Props {
  item: BatchItemStatus
}

const props = defineProps<Props>()

const emit = defineEmits<{
  openLot: [lotId: string]
}>()

const itemTitle = computed(() => {
  const { item } = props
  if (item.summary) {
    return item.summary.year
      ? `${item.summary.make} ${item.summary.model} ${item.summary.year}`
      : `${item.summary.make} ${item.summary.model}`
  }
  return item.preview_title || item.original_filename
})

const itemSubtitle = computed(() => {
  const { item } = props
  if (item.summary) {
    return `${item.summary.auction_house} #${item.summary.lot_number} · Оценка ${item.summary.overall_grade}`
  }
  if (item.status === 'failed') {
    return item.error_message || 'Не удалось распознать лист'
  }
  const stepLabel = formatTaskStepRu(item.current_step)
  return item.preview_title ? `${stepLabel} · ${item.original_filename}` : stepLabel
})

const verdictMeta = computed(() =>
  props.item.summary ? TRAFFIC_LIGHT_META[props.item.summary.verdict] : null,
)
</script>

<template>
  <!-- Ready Lot Row -->
  <BaseCard
    v-if="item.status === 'ready' && item.summary && verdictMeta"
    variant="surface"
    padding="none"
    interactive
    class="overflow-hidden"
  >
    <button
      type="button"
      class="focus-visible:outline-accent flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-3.5 text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
      @click="emit('openLot', item.summary.lot_id)"
    >
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="bg-success-bg text-success flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
        >
          <CheckCircle2 :size="17" :stroke-width="2" />
        </span>

        <div class="min-w-0">
          <div class="text-text-primary truncate text-[15px] font-semibold">
            {{ itemTitle }}
          </div>
          <div class="text-text-secondary truncate text-[12px]">
            {{ itemSubtitle }}
          </div>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-2.5">
        <div class="text-right">
          <div class="text-text-primary text-[14px] font-semibold tabular-nums">
            {{ formatRub(item.summary.turnkey_cost_rub) }}
          </div>
          <BaseBadge :variant="verdictMeta.badgeVariant" class="mt-0.5">
            {{ verdictMeta.label }}
          </BaseBadge>
        </div>

        <ChevronRight :size="16" class="text-text-tertiary shrink-0" />
      </div>
    </button>
  </BaseCard>

  <!-- Soft-deleted Ready Lot Row -->
  <BaseCard v-else-if="item.status === 'ready' && !item.summary" variant="surface" padding="none">
    <div class="flex items-center justify-between gap-3 px-4 py-3.5">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="bg-surface-inset text-text-secondary flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
        >
          <Trash2 :size="16" :stroke-width="2" />
        </span>
        <div class="min-w-0">
          <div class="text-text-primary truncate text-[14px] font-semibold">
            {{ itemTitle }}
          </div>
          <div class="text-text-secondary truncate text-[12px]">Лот удалён из списка</div>
        </div>
      </div>

      <BaseBadge variant="neutral">Удалён</BaseBadge>
    </div>
  </BaseCard>

  <!-- Failed Item Row -->
  <BaseCard v-else-if="item.status === 'failed'" variant="surface" padding="none">
    <div class="flex items-center justify-between gap-3 px-4 py-3.5">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="bg-danger-bg text-danger flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
        >
          <OctagonAlert :size="17" :stroke-width="2" />
        </span>
        <div class="min-w-0">
          <div class="text-text-primary truncate text-[14px] font-semibold">
            {{ itemTitle }}
          </div>
          <div class="text-danger truncate text-[12px]">
            {{ itemSubtitle }}
          </div>
        </div>
      </div>

      <BaseBadge variant="danger">Ошибка</BaseBadge>
    </div>
  </BaseCard>

  <!-- Processing / Queued Item Row -->
  <BaseCard v-else variant="surface" padding="none">
    <div class="flex items-center justify-between gap-3 px-4 py-3.5">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
          :class="
            item.status === 'processing'
              ? 'bg-info-bg text-info'
              : 'bg-surface-inset text-text-secondary'
          "
        >
          <Loader2
            v-if="item.status === 'processing'"
            :size="16"
            :stroke-width="2"
            class="animate-spin"
          />
          <Clock v-else :size="16" :stroke-width="2" />
        </span>

        <div class="min-w-0">
          <div class="text-text-primary truncate text-[14px] font-semibold">
            {{ itemTitle }}
          </div>
          <div class="text-text-secondary truncate text-[12px]">
            {{ itemSubtitle }}
          </div>
        </div>
      </div>

      <BaseBadge :variant="item.status === 'processing' ? 'info' : 'neutral'">
        {{ item.status === 'processing' ? 'Анализ' : 'В очереди' }}
      </BaseBadge>
    </div>
  </BaseCard>
</template>
