<script setup lang="ts">
import {
  AlertTriangle,
  CheckCircle2,
  OctagonAlert,
  RotateCcw,
  Search,
  SlidersHorizontal,
} from '@lucide/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

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
let searchTimer: number | null = null

const isSearchExpanded = computed(
  () => isSearchFocused.value || searchDraft.value.trim().length > 0,
)

const VERDICT_PILLS = computed(() => [
  {
    value: 'green' as const,
    label: 'Можно брать',
    count: props.availableFilters.counts_by_verdict.green ?? 0,
    icon: CheckCircle2,
    activeClass: 'bg-success-bg text-success border-success/25',
  },
  {
    value: 'yellow' as const,
    label: 'Под вопросом',
    count: props.availableFilters.counts_by_verdict.yellow ?? 0,
    icon: AlertTriangle,
    activeClass: 'bg-warning-bg text-warning border-warning/25',
  },
  {
    value: 'red' as const,
    label: 'Высокий риск',
    count: props.availableFilters.counts_by_verdict.red ?? 0,
    icon: OctagonAlert,
    activeClass: 'bg-danger-bg text-danger border-danger/25',
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
  <section aria-label="Поиск и фильтры лотов" class="flex flex-col gap-3">
    <div class="flex flex-wrap items-center justify-between gap-2.5">
      <div class="hidden items-center gap-1.5 lg:flex" role="group" aria-label="Быстрый светофор">
        <button
          type="button"
          class="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-sm border px-3 text-[13px] font-medium transition-colors"
          :class="
            selectedVerdict === null
              ? 'bg-text-primary border-text-primary text-surface'
              : 'bg-surface text-text-primary border-border hover:bg-surface-hover'
          "
          @click="emit('toggleVerdict', null)"
        >
          <span>Все</span>
          <span class="opacity-70">{{ availableFilters.total_lots_count }}</span>
        </button>

        <button
          v-for="pill in VERDICT_PILLS"
          :key="pill.value"
          type="button"
          class="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-sm border px-3 text-[13px] font-medium transition-colors"
          :class="
            selectedVerdict === pill.value
              ? pill.activeClass
              : 'bg-surface text-text-secondary border-border hover:bg-surface-hover hover:text-text-primary'
          "
          @click="emit('toggleVerdict', pill.value)"
        >
          <component :is="pill.icon" :size="14" :stroke-width="2" />
          <span>{{ pill.label }}</span>
          <span class="opacity-75">{{ pill.count }}</span>
        </button>

        <button
          type="button"
          class="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-sm border px-3 text-[13px] font-medium transition-colors"
          :class="
            onlyAnomalies
              ? 'bg-danger-bg text-danger border-danger/25'
              : 'bg-surface text-text-secondary border-border hover:bg-surface-hover hover:text-text-primary'
          "
          :aria-pressed="onlyAnomalies"
          @click="emit('toggleAnomaly')"
        >
          <AlertTriangle :size="14" :stroke-width="2" />
          <span>Аномалии</span>
        </button>
      </div>

      <div class="flex flex-1 items-center justify-end gap-2.5 lg:flex-none">
        <div
          class="min-w-0 flex-1 transition-[width] duration-200 ease-out lg:flex-none"
          :class="isSearchExpanded ? 'lg:w-76' : 'lg:w-48'"
        >
          <BaseInput
            v-model="searchDraft"
            type="search"
            inputmode="search"
            clearable
            :placeholder="isSearchExpanded ? 'Марка, кузов, лот...' : 'Поиск...'"
            @focus="isSearchFocused = true"
            @blur="isSearchFocused = false"
          >
            <template #prefix>
              <Search :size="16" :stroke-width="2" />
            </template>
          </BaseInput>
        </div>

        <div class="shrink-0 lg:hidden">
          <BaseButton
            variant="ghost"
            size="md"
            aria-label="Открыть фильтры и сортировку"
            class="bg-surface"
            @click="emit('openFilters')"
          >
            <template #icon-left>
              <SlidersHorizontal :size="16" :stroke-width="2" />
            </template>
            <span class="hidden sm:inline">Фильтры</span>
            <span
              v-if="activeFiltersCount > 0"
              class="bg-accent text-text-on-accent inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold"
            >
              {{ activeFiltersCount }}
            </span>
          </BaseButton>
        </div>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3">
      <div
        v-if="availableFilters.models.length > 0"
        class="-mx-4 flex flex-1 [scrollbar-width:none] items-center gap-2 overflow-x-auto px-4 pb-0.5 sm:mx-0 sm:px-0 [&::-webkit-scrollbar]:hidden"
        role="group"
        aria-label="Фильтр по модели"
      >
        <button
          type="button"
          class="inline-flex h-8 shrink-0 cursor-pointer items-center rounded-full border px-3 text-[13px] font-medium transition-colors"
          :class="
            selectedModel === null
              ? 'bg-accent border-accent text-text-on-accent'
              : 'bg-surface text-text-primary border-border hover:bg-surface-hover'
          "
          @click="emit('toggleModel', null)"
        >
          Все модели ({{ availableFilters.total_lots_count }})
        </button>

        <button
          v-for="modelItem in availableFilters.models"
          :key="modelItem.value"
          type="button"
          class="inline-flex h-8 shrink-0 cursor-pointer items-center rounded-full border px-3 text-[13px] font-medium transition-colors"
          :class="
            selectedModel === modelItem.value
              ? 'bg-accent border-accent text-text-on-accent'
              : 'bg-surface text-text-primary border-border hover:bg-surface-hover'
          "
          @click="emit('toggleModel', modelItem.value)"
        >
          {{ modelItem.value }} ({{ modelItem.count }})
        </button>
      </div>

      <div v-if="hasLoadedOnce" class="hidden shrink-0 items-center gap-2 lg:flex">
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
          variant="ghost"
          size="sm"
          pill
          aria-label="Открыть фильтры и сортировку"
          class="bg-surface"
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
