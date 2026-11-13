<script setup lang="ts">
import { AlertTriangle, CheckCircle2, OctagonAlert, RotateCcw } from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import {
  BaseButton,
  BaseSwitch,
  BottomSheet,
  SegmentedControl,
  type SegmentOption,
} from '@/components/ui'
import type {
  AvailableFilters,
  LotLifecycleFilter,
  LotSortBy,
  LotSortOrder,
  TrafficLightColor,
} from '@/types/api'

export interface LotFilterDraft {
  lifecycle: LotLifecycleFilter
  make: string | null
  verdict: TrafficLightColor | null
  onlyAnomalies: boolean
  sortBy: LotSortBy
  sortOrder: LotSortOrder
}

interface Props {
  availableFilters: AvailableFilters
  lifecycle: LotLifecycleFilter
  make: string | null
  verdict: TrafficLightColor | null
  onlyAnomalies: boolean
  sortBy: LotSortBy
  sortOrder: LotSortOrder
  previewFilters?: (draft: LotFilterDraft) => Promise<AvailableFilters | null>
}

const props = defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  apply: [draft: LotFilterDraft]
  reset: []
}>()

const draftLifecycle = ref<LotLifecycleFilter>(props.lifecycle)
const draftMake = ref<string | null>(props.make)
const draftVerdict = ref<TrafficLightColor | null>(props.verdict)
const draftOnlyAnomalies = ref(props.onlyAnomalies)
const draftSortBy = ref<LotSortBy>(props.sortBy)
const draftSortOrder = ref<LotSortOrder>(props.sortOrder)
const liveFilters = ref<AvailableFilters>(props.availableFilters)
let previewRequestSeq = 0

watch(
  open,
  (isOpen) => {
    if (!isOpen) return
    previewRequestSeq += 1
    draftLifecycle.value = props.lifecycle
    draftMake.value = props.make
    draftVerdict.value = props.verdict
    draftOnlyAnomalies.value = props.onlyAnomalies
    draftSortBy.value = props.sortBy
    draftSortOrder.value = props.sortOrder
    liveFilters.value = props.availableFilters
  },
  { immediate: true },
)

watch(
  () => props.availableFilters,
  (next) => {
    if (!open.value) {
      liveFilters.value = next
    }
  },
)

watch([draftLifecycle, draftMake, draftVerdict, draftOnlyAnomalies], async () => {
  if (!open.value || !props.previewFilters) return
  const seq = ++previewRequestSeq
  const next = await props.previewFilters({
    lifecycle: draftLifecycle.value,
    make: draftMake.value,
    verdict: draftVerdict.value,
    onlyAnomalies: draftOnlyAnomalies.value,
    sortBy: draftSortBy.value,
    sortOrder: draftSortOrder.value,
  })
  if (seq === previewRequestSeq && open.value && next) {
    liveFilters.value = next
  }
})

const LIFECYCLE_OPTIONS = computed<SegmentOption<LotLifecycleFilter>[]>(() => [
  { value: 'active', label: 'Активные' },
  {
    value: 'archived',
    label: 'Архив',
    badge:
      liveFilters.value.archived_lots_count > 0 ? liveFilters.value.archived_lots_count : undefined,
  },
  { value: 'all', label: 'Все' },
])

const SORT_OPTIONS: SegmentOption<LotSortBy>[] = [
  { value: 'created_at', label: 'Новые' },
  { value: 'net_benefit', label: 'Выгода' },
  { value: 'turnkey_cost', label: 'Цена' },
]

const ORDER_OPTIONS: SegmentOption<LotSortOrder>[] = [
  { value: 'desc', label: 'По убыванию' },
  { value: 'asc', label: 'По возрастанию' },
]

const makesTotalCount = computed(() =>
  liveFilters.value.makes.reduce((sum, item) => sum + item.count, 0),
)

const VERDICT_OPTIONS = computed(() => [
  {
    value: 'green' as const,
    label: 'Можно брать',
    count: liveFilters.value.counts_by_verdict.green ?? 0,
    icon: CheckCircle2,
    activeClass: 'bg-success-bg text-success border-success/30',
  },
  {
    value: 'yellow' as const,
    label: 'Под вопросом',
    count: liveFilters.value.counts_by_verdict.yellow ?? 0,
    icon: AlertTriangle,
    activeClass: 'bg-warning-bg text-warning border-warning/30',
  },
  {
    value: 'red' as const,
    label: 'Высокий риск',
    count: liveFilters.value.counts_by_verdict.red ?? 0,
    icon: OctagonAlert,
    activeClass: 'bg-danger-bg text-danger border-danger/30',
  },
])

function toggleVerdict(value: TrafficLightColor) {
  draftVerdict.value = draftVerdict.value === value ? null : value
}

function toggleMake(value: string) {
  draftMake.value = draftMake.value === value ? null : value
}

function handleApply() {
  emit('apply', {
    lifecycle: draftLifecycle.value,
    make: draftMake.value,
    verdict: draftVerdict.value,
    onlyAnomalies: draftOnlyAnomalies.value,
    sortBy: draftSortBy.value,
    sortOrder: draftSortOrder.value,
  })
  open.value = false
}

function handleReset() {
  draftLifecycle.value = 'active'
  draftMake.value = null
  draftVerdict.value = null
  draftOnlyAnomalies.value = false
  draftSortBy.value = 'created_at'
  draftSortOrder.value = 'desc'
  emit('reset')
  open.value = false
}
</script>

<template>
  <BottomSheet
    v-model:open="open"
    title="Фильтры и сортировка"
    subtitle="Уточните выборку лотов по статусу, вердикту и рискам"
    placement="right"
    max-width="md"
  >
    <div class="flex flex-col gap-5">
      <section class="flex flex-col gap-2">
        <span class="text-text-secondary text-[13px] font-medium">Жизненный цикл</span>
        <SegmentedControl
          v-model="draftLifecycle"
          :options="LIFECYCLE_OPTIONS"
          ariaLabel="Жизненный цикл лотов"
          full-width
          size="sm"
        />
      </section>

      <section class="flex flex-col gap-2">
        <span class="text-text-secondary text-[13px] font-medium">Вердикт</span>
        <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button
            v-for="option in VERDICT_OPTIONS"
            :key="option.value"
            type="button"
            :disabled="option.count === 0 && draftVerdict !== option.value"
            class="flex min-h-11 items-center justify-between gap-2 rounded-sm border px-2.5 py-2 text-left text-[13px] font-medium whitespace-nowrap transition-colors"
            :class="
              draftVerdict === option.value
                ? ['cursor-pointer', option.activeClass]
                : option.count === 0
                  ? 'bg-surface-inset text-text-muted cursor-not-allowed border-transparent opacity-50'
                  : 'bg-surface-inset text-text-primary hover:bg-surface-hover cursor-pointer border-transparent'
            "
            @click="toggleVerdict(option.value)"
          >
            <span class="flex items-center gap-1.5">
              <component :is="option.icon" :size="15" :stroke-width="2" class="shrink-0" />
              <span>{{ option.label }}</span>
            </span>
            <span
              class="text-[14px] font-semibold tabular-nums"
              :class="
                draftVerdict === option.value
                  ? 'opacity-90'
                  : option.count === 0
                    ? 'text-text-muted'
                    : 'text-text-primary'
              "
            >
              {{ option.count }}
            </span>
          </button>
        </div>
      </section>

      <section v-if="liveFilters.makes.length > 0" class="flex flex-col gap-2">
        <span class="text-text-secondary text-[13px] font-medium">Марка</span>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="min-h-9 cursor-pointer rounded-full border px-3 text-[13px] font-medium transition-colors"
            :class="
              draftMake === null
                ? 'bg-accent border-accent text-white'
                : 'bg-surface-inset text-text-primary hover:bg-surface-hover border-transparent'
            "
            @click="draftMake = null"
          >
            Все ({{ makesTotalCount }})
          </button>

          <button
            v-for="makeItem in liveFilters.makes"
            :key="makeItem.value"
            type="button"
            :disabled="makeItem.count === 0 && draftMake !== makeItem.value"
            class="min-h-9 rounded-full border px-3 text-[13px] font-medium transition-colors"
            :class="
              draftMake === makeItem.value
                ? 'bg-accent border-accent cursor-pointer text-white'
                : makeItem.count === 0
                  ? 'bg-surface-inset text-text-muted cursor-not-allowed border-transparent opacity-50'
                  : 'bg-surface-inset text-text-primary hover:bg-surface-hover cursor-pointer border-transparent'
            "
            @click="toggleMake(makeItem.value)"
          >
            {{ makeItem.value }} ({{ makeItem.count }})
          </button>
        </div>
      </section>

      <section class="border-border border-t pt-4">
        <BaseSwitch
          v-model="draftOnlyAnomalies"
          label="Только с аномалиями"
          description="Показать лоты с выявленными расхождениями и замечаниями на схеме"
        />
      </section>

      <section class="border-border flex flex-col gap-3 border-t pt-4">
        <span class="text-text-secondary text-[13px] font-medium">Сортировка</span>
        <SegmentedControl
          v-model="draftSortBy"
          :options="SORT_OPTIONS"
          ariaLabel="Критерий сортировки"
          full-width
          size="sm"
        />
        <SegmentedControl
          v-model="draftSortOrder"
          :options="ORDER_OPTIONS"
          ariaLabel="Порядок сортировки"
          full-width
          size="sm"
        />
      </section>
    </div>

    <template #footer>
      <div class="flex items-center gap-3">
        <BaseButton variant="secondary" class="shrink-0" @click="handleReset">
          <RotateCcw :size="16" />
          <span>Сбросить</span>
        </BaseButton>

        <BaseButton variant="primary" block @click="handleApply">Применить</BaseButton>
      </div>
    </template>
  </BottomSheet>
</template>
