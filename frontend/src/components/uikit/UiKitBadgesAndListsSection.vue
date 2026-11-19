<script setup lang="ts">
import {
  AlertTriangle,
  Anchor,
  Check,
  CircleAlert,
  FileText,
  Fuel,
  Gauge,
  Info,
  Package,
  Scale,
} from '@lucide/vue'

import { BaseBadge, BaseCard, InsetListGroup, InsetListItem } from '@/components/ui'

const emit = defineEmits<{
  openSheet: [topic: 'auction' | 'farpost']
}>()
</script>

<template>
  <BaseCard as="section" padding="lg" class="flex flex-col gap-4">
    <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
      <h2 class="text-text-primary text-[17px] font-semibold">3. Статус-капсулы (Soft Tints)</h2>
      <span class="text-text-secondary text-[12px]">
        Без обводки, иконки наследуют currentColor
      </span>
    </div>

    <div class="flex flex-wrap items-center gap-2.5">
      <BaseBadge variant="neutral">
        <template #icon>
          <Fuel :size="14" :stroke-width="2" />
        </template>
        Бензин 1.8L
      </BaseBadge>

      <BaseBadge variant="neutral">
        <template #icon>
          <Gauge :size="14" :stroke-width="2" />
        </template>
        58 240 км
      </BaseBadge>

      <BaseBadge variant="success">
        <template #icon>
          <Check :size="14" :stroke-width="2" />
        </template>
        Заводской окрас
      </BaseBadge>

      <BaseBadge variant="warning">
        <template #icon>
          <AlertTriangle :size="14" :stroke-width="2" />
        </template>
        Вторичный окрас (W2)
      </BaseBadge>

      <BaseBadge variant="danger">
        <template #icon>
          <CircleAlert :size="14" :stroke-width="2" />
        </template>
        Стоп-фактор (Ржавчина S2)
      </BaseBadge>

      <BaseBadge variant="info">
        <template #icon>
          <Info :size="14" :stroke-width="2" />
        </template>
        Проходной год (3–5 лет)
      </BaseBadge>
    </div>
  </BaseCard>

  <InsetListGroup title="4. Группированный список (Inset Grouped)">
    <InsetListItem
      title="Аукционный лист и перевод инспектора"
      subtitle="Нажмите, чтобы открыть Bottom Sheet"
      value="TAA Chubu #3142"
      squircle-color="#007AFF"
      interactive
      chevron
      @click="emit('openSheet', 'auction')"
    >
      <template #icon>
        <FileText :size="16" :stroke-width="2" />
      </template>
    </InsetListItem>

    <InsetListItem
      title="Морской фрахт и выгрузка СВХ"
      value="Toyama → Владивосток"
      squircle-color="#34C759"
    >
      <template #icon>
        <Anchor :size="16" :stroke-width="2" />
      </template>
    </InsetListItem>

    <InsetListItem title="Таможенная пошлина ЕАЭС" value="312 400 ₽" squircle-color="#FF9500">
      <template #icon>
        <Scale :size="16" :stroke-width="2" />
      </template>
    </InsetListItem>

    <InsetListItem
      title="Оценка ремонта на Farpost"
      subtitle="Контрактная дверь в цвет 070"
      value="от 31 000 ₽"
      squircle-color="#AF52DE"
      interactive
      chevron
      @click="emit('openSheet', 'farpost')"
    >
      <template #icon>
        <Package :size="16" :stroke-width="2" />
      </template>
    </InsetListItem>
  </InsetListGroup>
</template>
