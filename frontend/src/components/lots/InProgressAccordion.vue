<script setup lang="ts">
import { ChevronDown, Clock, Loader2 } from '@lucide/vue'
import { computed, ref, useId } from 'vue'

import { BaseBadge, BaseCard, InsetListGroup, InsetListItem } from '@/components/ui'
import type { InProgressItemPreview, InProgressSummary, ItemProcessingStatus } from '@/types/api'
import { formatCarCountRu, formatTaskStepRu } from '@/utils/formatters'

interface Props {
  summary: InProgressSummary
  defaultOpen?: boolean
  collapsible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  defaultOpen: false,
  collapsible: true,
})

const emit = defineEmits<{
  selectItem: [item: InProgressItemPreview]
}>()

const isOpen = ref(props.defaultOpen)
const uid = useId()
const contentId = `in-progress-panel-${uid}`

const expanded = computed(() => (props.collapsible ? isOpen.value : true))

const STATUS_META: Record<
  ItemProcessingStatus,
  { label: string; variant: 'info' | 'neutral' | 'success' | 'danger'; squircleColor: string }
> = {
  queued: { label: 'В очереди', variant: 'neutral', squircleColor: '#6B7280' },
  processing: { label: 'Анализ', variant: 'info', squircleColor: '#1D4ED8' },
  ready: { label: 'Готово', variant: 'success', squircleColor: '#15803D' },
  failed: { label: 'Ошибка', variant: 'danger', squircleColor: '#B91C1C' },
}

function toggleExpanded() {
  if (!props.collapsible) return
  isOpen.value = !isOpen.value
}
</script>

<template>
  <BaseCard
    v-if="summary.total_processing_lots > 0"
    as="section"
    variant="surface"
    padding="none"
    class="overflow-hidden"
  >
    <button
      type="button"
      class="hover:bg-surface-hover flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors"
      :class="collapsible ? 'cursor-pointer' : 'cursor-default'"
      :aria-expanded="expanded"
      :aria-controls="contentId"
      @click="toggleExpanded"
    >
      <div class="flex min-w-0 items-center gap-2.5">
        <span
          class="bg-warning-bg text-warning flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
        >
          <Loader2 :size="16" :stroke-width="2" class="animate-spin" />
        </span>

        <div class="min-w-0">
          <div class="text-text-primary text-[14px] leading-snug font-semibold">
            В обработке {{ formatCarCountRu(summary.total_processing_lots) }}
          </div>
          <div class="text-text-secondary truncate text-[12px] leading-snug">
            Предположительно это займёт ~30 секунд
          </div>
        </div>
      </div>

      <ChevronDown
        v-if="collapsible"
        :size="18"
        class="text-text-tertiary shrink-0 transition-transform duration-200"
        :class="expanded ? 'rotate-180' : ''"
      />
    </button>

    <div
      v-show="expanded"
      :id="contentId"
      class="border-border bg-surface-inset/50 border-t px-3 py-2.5"
    >
      <InsetListGroup>
        <InsetListItem
          v-for="(item, index) in summary.items"
          :key="`${item.batch_id}-${item.lot_id ?? index}`"
          :title="item.display_title"
          :subtitle="formatTaskStepRu(item.current_step)"
          :squircle-color="STATUS_META[item.status].squircleColor"
          interactive
          chevron
          @click="emit('selectItem', item)"
        >
          <template #icon>
            <Clock :size="15" :stroke-width="1.9" />
          </template>

          <template #trailing>
            <BaseBadge :variant="STATUS_META[item.status].variant" size="sm">
              {{ STATUS_META[item.status].label }}
            </BaseBadge>
          </template>
        </InsetListItem>
      </InsetListGroup>
    </div>
  </BaseCard>
</template>
