<script setup lang="ts">
import { ChevronDown, ChevronRight, Clock, Loader2 } from '@lucide/vue'
import { computed, useId } from 'vue'

import { BaseBadge } from '@/components/ui'
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

const isOpen = defineModel<boolean>('open', { default: false })
if (props.defaultOpen && !isOpen.value) {
  isOpen.value = true
}

const emit = defineEmits<{
  selectItem: [item: InProgressItemPreview]
}>()

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
  <section
    v-if="summary.total_processing_lots > 0"
    aria-label="Автомобили в обработке"
    class="border-border bg-surface shadow-card overflow-hidden rounded-md border"
  >
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left transition-colors"
      :class="collapsible ? 'hover:bg-surface-hover/60 cursor-pointer' : 'cursor-default'"
      :aria-expanded="expanded"
      :aria-controls="contentId"
      @click="toggleExpanded"
    >
      <div class="flex min-w-0 items-center gap-2.5">
        <span
          class="bg-warning-bg text-warning flex h-7 w-7 shrink-0 items-center justify-center rounded-sm"
        >
          <Loader2 :size="15" :stroke-width="2" class="animate-spin" />
        </span>

        <div class="min-w-0">
          <div class="text-text-primary text-[13px] leading-snug font-semibold">
            В обработке {{ formatCarCountRu(summary.total_processing_lots) }}
          </div>
          <div class="text-text-secondary truncate text-[12px] leading-snug">
            Предположительно это займёт ~30 секунд
          </div>
        </div>
      </div>

      <ChevronDown
        v-if="collapsible"
        :size="17"
        class="text-text-tertiary shrink-0 transition-transform duration-200"
        :class="expanded ? 'rotate-180' : ''"
      />
    </button>

    <div
      v-show="expanded"
      :id="contentId"
      class="border-border bg-surface-inset/50 border-t px-3 py-2.5"
    >
      <ul class="grid grid-cols-1 gap-2" :class="summary.items.length > 1 ? 'md:grid-cols-2' : ''">
        <li
          v-for="(item, index) in summary.items"
          :key="`${item.batch_id}-${item.lot_id ?? index}`"
          class="min-w-0"
        >
          <button
            type="button"
            class="border-border bg-surface hover:border-border-strong hover:bg-surface-hover/60 active:bg-surface-inset/70 focus-visible:outline-accent flex w-full min-w-0 cursor-pointer items-center justify-between gap-2.5 rounded-sm border px-3 py-2 text-left transition-colors duration-[var(--duration-quick)] ease-[var(--ease-out)] focus-visible:outline-2 focus-visible:outline-offset-[-2px]"
            @click="emit('selectItem', item)"
          >
            <div class="flex min-w-0 flex-1 items-center gap-2.5">
              <div
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] text-white"
                :style="{ backgroundColor: STATUS_META[item.status].squircleColor }"
                aria-hidden="true"
              >
                <Loader2
                  v-if="item.status === 'processing'"
                  :size="14"
                  :stroke-width="2"
                  class="animate-spin"
                />
                <Clock v-else :size="14" :stroke-width="1.9" />
              </div>

              <div class="min-w-0 flex-1">
                <div class="text-text-primary truncate text-[14px] leading-snug font-medium">
                  {{ item.display_title }}
                </div>
                <div class="text-text-secondary truncate text-[12px] leading-snug">
                  {{ formatTaskStepRu(item.current_step) }}
                </div>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-1.5">
              <BaseBadge :variant="STATUS_META[item.status].variant" size="sm">
                {{ STATUS_META[item.status].label }}
              </BaseBadge>
              <ChevronRight :size="15" :stroke-width="2" class="text-text-muted shrink-0" />
            </div>
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>
