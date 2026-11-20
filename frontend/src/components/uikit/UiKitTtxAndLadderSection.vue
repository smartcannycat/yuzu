<script setup lang="ts">
import { computed } from 'vue'

import { BaseCard, CostLadder, TtxGrid, type CostLadderStep, type TtxItem } from '@/components/ui'

interface Props {
  isPersonalUtil: boolean
}

const props = defineProps<Props>()

const ttxItems: TtxItem[] = [
  { label: 'Кузов', value: 'NRE210-2005418' },
  { label: 'Год выпуска', value: '2020 (октябрь)' },
  { label: 'Двигатель', value: '1.2 л Turbo / 116 л.с.' },
  { label: 'Привод', value: 'Передний (FF)' },
  { label: 'Пробег', value: '58 240 км' },
  { label: 'Оценка лота', value: '3.5 / Салон B' },
]

const costSteps = computed<CostLadderStep[]>(() => [
  { label: 'Ставка на аукционе FOB', value: '1 060 000 ¥', active: true },
  { label: 'Фрахт и услуги в порту', value: '95 000 ₽' },
  { label: 'Таможенная пошлина ЕАЭС', value: '312 400 ₽' },
  {
    label: 'Утилизационный сбор РФ',
    hint: props.isPersonalUtil ? 'Льготный тариф (<= 160 л.с.)' : 'Коммерческий тариф ПП № 1255',
    value: props.isPersonalUtil ? '5 200 ₽' : '528 000 ₽',
  },
])

const totalTurnkey = computed(() => (props.isPersonalUtil ? '1 104 899 ₽' : '1 627 699 ₽'))
</script>

<template>
  <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
    <BaseCard as="section" padding="lg" class="flex flex-col gap-4">
      <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
        <h2 class="text-text-primary text-[17px] font-semibold">5. Сетка ТТХ</h2>
        <span class="text-text-secondary text-[12px]">2 колонки без вертикальных рамок</span>
      </div>
      <TtxGrid :items="ttxItems" />
    </BaseCard>

    <BaseCard as="section" padding="lg" class="flex flex-col gap-4">
      <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
        <h2 class="text-text-primary text-[17px] font-semibold">6. Финансовая лестница</h2>
        <span class="text-text-secondary text-[12px]">Связана со свитчем iOS 26 выше</span>
      </div>
      <CostLadder
        :steps="costSteps"
        total-label="Итого под ключ во Владивостоке"
        :total-value="totalTurnkey"
      />
    </BaseCard>
  </div>
</template>
