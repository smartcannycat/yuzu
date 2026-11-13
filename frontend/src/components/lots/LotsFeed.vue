<script setup lang="ts">
import { FileUp, OctagonAlert, RotateCcw, SearchX } from '@lucide/vue'

import LotCard from '@/components/lots/LotCard.vue'
import { CapyMascot } from '@/components/mascot'
import { BaseButton, BaseCard } from '@/components/ui'
import type { LotSummary } from '@/types/api'

interface Props {
  items: LotSummary[]
  isLoading: boolean
  isLoadingMore: boolean
  hasLoadedOnce: boolean
  hasMore: boolean
  hasAnyActiveFilter: boolean
  errorMessage: string | null
}

defineProps<Props>()

const emit = defineEmits<{
  selectLot: [lot: LotSummary]
  retry: []
  resetFilters: []
  openUpload: []
  loadMore: []
}>()
</script>

<template>
  <main class="flex flex-1 flex-col gap-4">
    <BaseCard v-if="errorMessage" padding="lg" class="flex flex-col items-start gap-3">
      <div class="text-danger flex items-center gap-2 text-[15px] font-semibold">
        <OctagonAlert :size="18" />
        <span>Не удалось загрузить ленту лотов</span>
      </div>
      <p class="text-text-secondary text-[14px]">{{ errorMessage }}</p>
      <BaseButton variant="secondary" size="sm" @click="emit('retry')">Повторить</BaseButton>
    </BaseCard>

    <div
      v-else-if="isLoading && !hasLoadedOnce"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-5"
      aria-label="Загрузка лотов"
    >
      <BaseCard v-for="n in 4" :key="n" padding="md" class="flex gap-4">
        <div class="bg-surface-inset h-[94px] w-[68px] shrink-0 animate-pulse rounded-sm" />
        <div class="flex flex-1 flex-col gap-2.5">
          <div class="bg-surface-inset h-5 w-2/3 animate-pulse rounded-sm" />
          <div class="bg-surface-inset h-3.5 w-5/6 animate-pulse rounded-sm" />
          <div class="bg-surface-inset h-5 w-1/2 animate-pulse rounded-sm" />
          <div class="bg-surface-inset mt-2 h-6 w-full animate-pulse rounded-sm" />
        </div>
      </BaseCard>
    </div>

    <BaseCard
      v-else-if="hasLoadedOnce && items.length === 0 && !hasAnyActiveFilter"
      padding="lg"
      class="flex flex-col items-center gap-4 py-10 text-center"
    >
      <CapyMascot state="sleeping" size="hero" badge-text="Готов к анализу первого листа" />
      <div class="flex max-w-md flex-col gap-1.5">
        <h2 class="text-text-primary text-[19px] font-semibold">
          У вас пока нет просчитанных лотов
        </h2>
        <p class="text-text-secondary text-[14px] leading-relaxed">
          Загрузите фото или скан японского аукционного листа — Юдзу переведёт заметки, оценит риски
          и посчитает цену под ключ до Владивостока.
        </p>
      </div>
      <BaseButton variant="primary" size="lg" @click="emit('openUpload')">
        <template #icon-left>
          <FileUp :size="18" />
        </template>
        Загрузить первый лист
      </BaseButton>
    </BaseCard>

    <BaseCard
      v-else-if="hasLoadedOnce && items.length === 0 && hasAnyActiveFilter"
      padding="lg"
      class="flex flex-col items-center gap-3 py-10 text-center"
    >
      <span
        class="bg-surface-inset text-text-tertiary flex h-12 w-12 items-center justify-center rounded-full"
      >
        <SearchX :size="24" :stroke-width="1.8" />
      </span>
      <div class="flex max-w-sm flex-col gap-1">
        <h2 class="text-text-primary text-[17px] font-semibold">Лоты не найдены</h2>
        <p class="text-text-secondary text-[14px]">
          По текущему поисковому запросу или фильтрам совпадений нет.
        </p>
      </div>
      <BaseButton variant="secondary" size="md" @click="emit('resetFilters')">
        <template #icon-left>
          <RotateCcw :size="15" />
        </template>
        Сбросить фильтры
      </BaseButton>
    </BaseCard>

    <template v-else>
      <div
        class="grid grid-cols-1 gap-4 transition-opacity duration-150 md:grid-cols-2 md:gap-5"
        :class="isLoading ? 'opacity-65' : 'opacity-100'"
      >
        <LotCard
          v-for="lot in items"
          :key="lot.lot_id"
          :lot="lot"
          @select="emit('selectLot', $event)"
        />
      </div>

      <div v-if="hasMore" class="flex justify-center pt-2">
        <BaseButton
          variant="secondary"
          size="md"
          :loading="isLoadingMore"
          @click="emit('loadMore')"
        >
          Показать ещё
        </BaseButton>
      </div>
    </template>
  </main>
</template>
