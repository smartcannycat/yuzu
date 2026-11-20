<script setup lang="ts">
import { Calculator, FileText, Trash2 } from '@lucide/vue'

import { BaseButton, BaseCard } from '@/components/ui'

interface Props {
  isCalculating: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  triggerLoading: []
}>()
</script>

<template>
  <BaseCard as="section" padding="lg" class="flex flex-col gap-5">
    <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
      <h2 class="text-text-primary text-[17px] font-semibold">1. Кнопки и состояния</h2>
      <span class="text-text-secondary text-[12px]">L (48px), M (40px), S (32px)</span>
    </div>

    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <BaseButton
          variant="primary"
          size="lg"
          :loading="isCalculating"
          @click="emit('triggerLoading')"
        >
          <template #icon-left>
            <Calculator :size="18" :stroke-width="2" />
          </template>
          {{ isCalculating ? 'Пересчёт...' : 'Рассчитать под ключ' }}
        </BaseButton>

        <BaseButton variant="secondary" size="lg">
          <template #icon-left>
            <FileText :size="18" :stroke-width="2" />
          </template>
          Оригинал листа
        </BaseButton>

        <BaseButton variant="ghost" size="lg"> Сравнить на Drom </BaseButton>

        <BaseButton variant="primary" size="lg" disabled> Заблокировано </BaseButton>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <BaseButton variant="primary" size="md">Фильтры</BaseButton>
        <BaseButton variant="secondary" size="md">Подробнее</BaseButton>
        <BaseButton variant="destructive" size="md">
          <template #icon-left>
            <Trash2 :size="15" :stroke-width="2" />
          </template>
          Удалить лот
        </BaseButton>
        <BaseButton variant="secondary" size="sm">Farpost</BaseButton>
        <BaseButton variant="ghost" size="sm">Экспорт PDF</BaseButton>
      </div>
    </div>
  </BaseCard>
</template>
