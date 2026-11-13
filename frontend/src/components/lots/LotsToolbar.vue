<script setup lang="ts">
import {
  AlertTriangle,
  CheckCircle2,
  OctagonAlert,
  RotateCcw,
  Search,
  SlidersHorizontal,
} from '@lucide/vue'
import { useResizeObserver } from '@vueuse/core'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'

import { BaseButton, BaseInput } from '@/components/ui'
import type { AvailableFilters, TrafficLightColor } from '@/types/api'

interface Props {
  query: string
  selectedModel: string | null
  selectedVerdict: TrafficLightColor | null
  onlyAnomalies: boolean
  activeFiltersCount: number
  hasAnyActiveFilter: boolean
  hasLoadedOnce: boolean
  availableFilters: AvailableFilters
}

const props = defineProps<Props>()

const emit = defineEmits<{
  search: [query: string]
  toggleModel: [model: string | null]
  toggleVerdict: [verdict: TrafficLightColor | null]
  toggleAnomaly: []
  openFilters: []
  resetFilters: []
}>()

const searchDraft = ref(props.query)
const isSearchFocused = ref(false)
const modelsScrollerRef = useTemplateRef<HTMLDivElement>('modelsScrollerRef')
const canScrollLeft = ref(false)
const canScrollRight = ref(false)
let searchTimer: number | null = null

function updateScrollFade() {
  const el = modelsScrollerRef.value
  if (!el) {
    canScrollLeft.value = false
    canScrollRight.value = false
    return
  }
  const maxScroll = el.scrollWidth - el.clientWidth
  canScrollLeft.value = el.scrollLeft > 2
  canScrollRight.value = maxScroll > 2 && el.scrollLeft < maxScroll - 2
}

useResizeObserver(modelsScrollerRef, updateScrollFade)

onMounted(() => {
  void nextTick(updateScrollFade)
})

watch(
  () => props.availableFilters.models,
  () => {
    void nextTick(updateScrollFade)
  },
  { deep: true },
)

const modelsTotalCount = computed(() =>
  props.availableFilters.models.reduce((sum, item) => sum + item.count, 0),
)

const verdictTotalCount = computed(
  () =>
    (props.availableFilters.counts_by_verdict.green ?? 0) +
    (props.availableFilters.counts_by_verdict.yellow ?? 0) +
    (props.availableFilters.counts_by_verdict.red ?? 0),
)

const isSearchExpanded = computed(
  () => isSearchFocused.value || searchDraft.value.trim().length > 0,
)

const VERDICT_PILLS = computed(() => [
  {
    value: 'green' as const,
    label: 'Можно брать',
    count: props.availableFilters.counts_by_verdict.green ?? 0,
    icon: CheckCircle2,
    activeClass: 'bg-success-bg text-success shadow-segment',
  },
  {
    value: 'yellow' as const,
    label: 'Под вопросом',
    count: props.availableFilters.counts_by_verdict.yellow ?? 0,
    icon: AlertTriangle,
    activeClass: 'bg-warning-bg text-warning shadow-segment',
  },
  {
    value: 'red' as const,
    label: 'Высокий риск',
    count: props.availableFilters.counts_by_verdict.red ?? 0,
    icon: OctagonAlert,
    activeClass: 'bg-danger-bg text-danger shadow-segment',
  },
])

function clearSearchTimer() {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer)
    searchTimer = null
  }
}

watch(
  () => props.query,
  (externalQuery) => {
    if (externalQuery !== searchDraft.value.trim()) {
      clearSearchTimer()
      searchDraft.value = externalQuery
    }
  },
)

watch(searchDraft, (nextValue) => {
  clearSearchTimer()
  const trimmed = nextValue.trim()

  if (trimmed === props.query) {
    return
  }

  if (trimmed.length === 0) {
    emit('search', '')
    return
  }

  searchTimer = window.setTimeout(() => {
    emit('search', trimmed)
  }, 260)
})

onBeforeUnmount(() => {
  clearSearchTimer()
})

function handleResetClick() {
  clearSearchTimer()
  searchDraft.value = ''
  emit('resetFilters')
}
</script>

<template>
  <section
    aria-label="Поиск и фильтры лотов"
    class="bg-surface border-border shadow-card flex flex-col gap-2.5 rounded-md border p-3 sm:p-3.5"
  >
    <div class="flex flex-wrap items-center justify-between gap-2.5">
      <div class="hidden items-center gap-2 lg:flex">
        <div
          class="bg-surface-inset inline-flex h-10 items-center gap-1 rounded-sm p-1"
          role="group"
          aria-label="Быстрый светофор"
        >
          <button
            type="button"
            class="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-[6px] px-2.5 text-[13px] font-medium transition-all"
            :class="
              selectedVerdict === null
                ? 'bg-surface text-text-primary shadow-segment'
                : 'text-text-secondary hover:text-text-primary'
            "
            @click="emit('toggleVerdict', null)"
          >
            <span>Все</span>
            <span class="opacity-65">{{ verdictTotalCount }}</span>
          </button>

          <button
            v-for="pill in VERDICT_PILLS"
            :key="pill.value"
            type="button"
            :disabled="pill.count === 0 && selectedVerdict !== pill.value"
            class="inline-flex h-8 items-center gap-1.5 rounded-[6px] px-2.5 text-[13px] font-medium transition-all"
            :class="
              selectedVerdict === pill.value
                ? ['cursor-pointer', pill.activeClass]
                : pill.count === 0
                  ? 'text-text-muted cursor-not-allowed opacity-55'
                  : 'text-text-secondary hover:text-text-primary cursor-pointer'
            "
            @click="emit('toggleVerdict', pill.value)"
          >
            <component :is="pill.icon" :size="14" :stroke-width="2" />
            <span>{{ pill.label }}</span>
            <span class="opacity-75">{{ pill.count }}</span>
          </button>
        </div>

        <button
          type="button"
          class="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-sm px-3 text-[13px] font-medium transition-colors"
          :class="
            onlyAnomalies
              ? 'bg-danger-bg text-danger ring-danger/25 ring-1'
              : 'bg-surface-inset text-text-secondary hover:bg-border/70 hover:text-text-primary'
          "
          :aria-pressed="onlyAnomalies"
          @click="emit('toggleAnomaly')"
        >
          <AlertTriangle :size="14" :stroke-width="2" />
          <span>Аномалии</span>
        </button>
      </div>

      <div class="flex flex-1 items-center justify-end gap-2 lg:flex-none">
        <div
          class="min-w-0 flex-1 transition-[width] duration-200 ease-out lg:flex-none"
          :class="isSearchExpanded ? 'lg:w-80' : 'lg:w-64'"
        >
          <BaseInput
            v-model="searchDraft"
            variant="inset"
            size="md"
            type="search"
            inputmode="search"
            clearable
            placeholder="Марка, кузов, лот..."
            @focus="isSearchFocused = true"
            @blur="isSearchFocused = false"
          >
            <template #prefix>
              <Search :size="16" :stroke-width="2" />
            </template>
          </BaseInput>
        </div>

        <div class="shrink-0 lg:hidden">
          <button
            type="button"
            aria-label="Открыть фильтры и сортировку"
            class="bg-surface-inset text-text-primary hover:bg-border active:bg-border-strong/60 focus-visible:outline-accent relative inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-sm text-[14px] font-medium whitespace-nowrap transition-[background-color,scale] duration-[var(--duration-quick)] ease-[var(--ease-out)] select-none focus-visible:outline-2 focus-visible:outline-offset-2 active:scale-[0.98] sm:w-auto sm:gap-2 sm:px-3.5"
            @click="emit('openFilters')"
          >
            <SlidersHorizontal :size="17" :stroke-width="2" class="shrink-0" aria-hidden="true" />
            <span class="hidden sm:inline">Фильтры</span>
            <span
              v-if="activeFiltersCount > 0"
              class="bg-accent text-text-on-accent absolute -top-1 -right-1 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-semibold sm:static sm:h-5 sm:min-w-5 sm:px-1.5 sm:text-[11px]"
            >
              {{ activeFiltersCount }}
            </span>
          </button>
        </div>
      </div>
    </div>

    <div class="border-border flex items-center justify-between gap-3 border-t pt-2.5">
      <div v-if="availableFilters.models.length > 0" class="relative min-w-0 flex-1">
        <div
          ref="modelsScrollerRef"
          class="flex [scrollbar-width:none] items-center gap-1.5 overflow-x-auto [&::-webkit-scrollbar]:hidden"
          role="group"
          aria-label="Фильтр по модели"
          @scroll.passive="updateScrollFade"
        >
          <button
            type="button"
            class="inline-flex h-8 shrink-0 cursor-pointer items-center rounded-full px-3 text-[13px] font-medium transition-colors"
            :class="
              selectedModel === null
                ? 'bg-accent text-text-on-accent'
                : 'bg-surface-inset text-text-primary hover:bg-border/70'
            "
            @click="emit('toggleModel', null)"
          >
            Все модели ({{ modelsTotalCount }})
          </button>

          <button
            v-for="modelItem in availableFilters.models"
            :key="modelItem.value"
            type="button"
            class="inline-flex h-8 shrink-0 cursor-pointer items-center rounded-full px-3 text-[13px] font-medium transition-colors"
            :class="
              selectedModel === modelItem.value
                ? 'bg-accent text-text-on-accent'
                : 'bg-surface-inset text-text-primary hover:bg-border/70'
            "
            @click="emit('toggleModel', modelItem.value)"
          >
            {{ modelItem.value }} ({{ modelItem.count }})
          </button>
        </div>

        <span
          aria-hidden="true"
          class="from-surface via-surface/85 pointer-events-none absolute inset-y-0 left-0 w-7 bg-gradient-to-r to-transparent transition-opacity duration-150 sm:w-8"
          :class="canScrollLeft ? 'opacity-100' : 'opacity-0'"
        />
        <span
          aria-hidden="true"
          class="from-surface via-surface/85 pointer-events-none absolute inset-y-0 right-0 w-7 bg-gradient-to-l to-transparent transition-opacity duration-150 sm:w-8"
          :class="canScrollRight ? 'opacity-100' : 'opacity-0'"
        />
      </div>

      <div v-if="hasLoadedOnce" class="hidden shrink-0 items-center gap-1.5 lg:flex">
        <button
          v-if="hasAnyActiveFilter"
          type="button"
          class="text-accent hover:text-accent-hover inline-flex h-8 cursor-pointer items-center gap-1 px-2 text-[13px] font-medium"
          @click="handleResetClick"
        >
          <RotateCcw :size="13" />
          <span>Сбросить</span>
        </button>

        <BaseButton
          variant="secondary"
          size="sm"
          pill
          aria-label="Открыть фильтры и сортировку"
          @click="emit('openFilters')"
        >
          <template #icon-left>
            <SlidersHorizontal :size="14" :stroke-width="2" />
          </template>
          <span>Фильтры</span>
          <span
            v-if="activeFiltersCount > 0"
            class="bg-accent text-text-on-accent inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold"
          >
            {{ activeFiltersCount }}
          </span>
        </BaseButton>
      </div>
    </div>
  </section>
</template>
