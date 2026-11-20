<script setup lang="ts">
import { Search } from '@lucide/vue'
import { computed, ref } from 'vue'

import {
  BaseCard,
  BaseInput,
  BaseSwitch,
  SegmentedControl,
  type SegmentOption,
} from '@/components/ui'

type LotTab = 'general' | 'tech' | 'economics'

const isPersonalUtil = defineModel<boolean>('isPersonalUtil', { required: true })

const frameIdInput = ref('NRE210-2005418')
const searchInput = ref('')
const yearMonthInput = ref('2018/13')
const activeTab = ref<LotTab>('general')

const tabOptions: SegmentOption<LotTab>[] = [
  { value: 'general', label: 'Общий' },
  { value: 'tech', label: 'Техника', badge: 4 },
  { value: 'economics', label: 'Экономика' },
]

const yearMonthError = computed(() => {
  if (!yearMonthInput.value) return undefined
  return /^\d{4}\/(0[1-9]|1[0-2])$/.test(yearMonthInput.value)
    ? undefined
    : 'Некорректный месяц (формат ГГГГ/ММ, от 01 до 12)'
})
</script>

<template>
  <BaseCard as="section" padding="lg" class="flex flex-col gap-6">
    <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
      <h2 class="text-text-primary text-[17px] font-semibold">
        2. Поля ввода, свитч iOS 26 и Segmented Control
      </h2>
      <span class="text-text-secondary text-[12px]">
        Клавиатурная навигация и 16px без зума iOS
      </span>
    </div>

    <div class="grid grid-cols-1 gap-5 md:grid-cols-2">
      <BaseInput
        v-model="frameIdInput"
        label="Номер кузова (Frame ID)"
        placeholder="Например, NHP10-2094112"
        helper-text="Формат: серия кузова и 7 цифр"
        clearable
      />

      <BaseInput
        v-model="searchInput"
        label="Поиск лота на аукционе"
        placeholder="USS Tokyo, лот #4102"
        helper-text="Автоопределение аукционного дома"
        clearable
      >
        <template #prefix>
          <Search :size="17" :stroke-width="2" />
        </template>
      </BaseInput>

      <BaseInput
        v-model="yearMonthInput"
        label="Год и месяц выпуска"
        placeholder="2020/10"
        :error="yearMonthError"
        helper-text="Корректный формат: ГГГГ/ММ"
      />

      <div class="flex flex-col justify-center gap-2">
        <span class="text-text-secondary text-[13px] font-medium">
          Утилизационный сбор РФ (iOS 26 Switch)
        </span>
        <BaseSwitch
          v-model="isPersonalUtil"
          label="Для личного пользования"
          :description="isPersonalUtil ? 'Льготный тариф 5 200 ₽' : 'Коммерческий тариф 528 000 ₽'"
        />
      </div>
    </div>

    <div class="border-border flex flex-col gap-2 border-t pt-4">
      <span class="text-text-secondary text-[13px] font-medium">
        Переключатель вкладок (стрелки влево/вправо, Home/End)
      </span>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <SegmentedControl
          v-model="activeTab"
          :options="tabOptions"
          ariaLabel="Разделы карточки лота"
        />
        <span class="text-text-secondary text-[13px]">
          Активная вкладка:
          <strong class="text-text-primary font-semibold">{{ activeTab }}</strong>
        </span>
      </div>
    </div>
  </BaseCard>
</template>
