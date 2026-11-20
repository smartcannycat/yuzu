<script setup lang="ts">
import { AlertTriangle, CircleAlert, ShieldCheck } from '@lucide/vue'
import { computed, ref } from 'vue'

import { BaseBadge, BaseButton, BaseCard, CapyMascot, type CapyState } from '@/components/ui'

interface MascotDemoOption {
  state: CapyState
  label: string
  screen: string
  contract: string
  badge: string
}

const mascotDemoOptions: readonly MascotDemoOption[] = [
  {
    state: 'sleeping',
    label: '1. Сон (Dropzone)',
    screen: 'Экран 2 / Пустой стейт',
    contract: 'MascotMood.SLEEPING • selectedFiles.length === 0',
    badge: 'Ожидание загрузки аукционных листов',
  },
  {
    state: 'peeking',
    label: '1б. Готовность (Peeking)',
    screen: 'Экран 2 (выбраны 1..10 фото)',
    contract: 'selectedFiles.length > 0 || isDragOver',
    badge: 'Выбрано 4 листа • Готова к расчёту',
  },
  {
    state: 'thinking',
    label: '2. Аудит (Thinking)',
    screen: 'Экран 3: Очередь DAG',
    contract: 'BatchStatus.PROCESSING • MascotMood.THINKING',
    badge: 'Распознаём лоты... 3/4',
  },
  {
    state: 'green',
    label: '3. Чистый лот (Green)',
    screen: 'Экран 4 / Финал очереди',
    contract: 'TrafficLightColor.GREEN • MascotMood.HAPPY',
    badge: 'Вердикт Юдзу: Чистый лот (+415 101 ₽)',
  },
  {
    state: 'yellow',
    label: '4. Внимание (Yellow)',
    screen: 'Экран 4 / Partial Failed',
    contract: 'TrafficLightColor.YELLOW • MascotMood.CONFUSED',
    badge: 'Вердикт Юдзу: Умеренная выгода / Окрас W2',
  },
  {
    state: 'red',
    label: '5. Стоп-фактор (Red)',
    screen: 'Экран 4: Safety Filter',
    contract: 'TrafficLightColor.RED • MascotMood.WARNING',
    badge: 'Вердикт Юдзу: Оценка R • Стоп-фактор!',
  },
  {
    state: 'error',
    label: '6. Ошибка OCR (Shrug)',
    screen: 'Отбраковка Gatekeeper',
    contract: 'BatchStatus.FAILED • ItemProcessingStatus.FAILED',
    badge: 'Фото размыто или не является бланком',
  },
]

const demoMascotState = ref<CapyState>('sleeping')
const activeMascotMeta = computed(
  () => mascotDemoOptions.find((o) => o.state === demoMascotState.value) ?? mascotDemoOptions[0]!,
)
</script>

<template>
  <BaseCard as="section" padding="lg" class="flex flex-col gap-5">
    <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
      <h2 class="text-text-primary text-[17px] font-semibold">
        7. Живой маскот Юдзу («Дзен-Инспектор») и карточки вердикта
      </h2>
      <span class="text-text-secondary text-[12px]">
        Единый SVG-риг • 6 состояний + Peeking • Duolingo Shape Language
      </span>
    </div>

    <BaseCard
      variant="inset"
      padding="md"
      class="grid grid-cols-1 items-center gap-5 lg:grid-cols-12"
    >
      <div
        class="bg-surface border-border shadow-card flex flex-col items-center justify-center rounded-md border py-5 lg:col-span-5"
      >
        <CapyMascot :state="demoMascotState" size="hero" :badge-text="activeMascotMeta.badge" />
      </div>

      <div class="flex flex-col gap-3.5 lg:col-span-7">
        <div class="flex flex-col gap-1">
          <span class="text-text-secondary text-[12px] font-medium">
            Точка контакта: {{ activeMascotMeta.screen }}
          </span>
          <p class="text-text-primary text-[14px] font-semibold">
            Контракт API:
            <code class="text-accent font-mono text-[13px]">{{ activeMascotMeta.contract }}</code>
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <BaseButton
            v-for="item in mascotDemoOptions"
            :key="item.state"
            :variant="demoMascotState === item.state ? 'primary' : 'secondary'"
            size="sm"
            @click="demoMascotState = item.state"
          >
            {{ item.label }}
          </BaseButton>
        </div>

        <p class="text-text-secondary text-[13px] leading-relaxed">
          Все состояния построены на едином векторном риге спящей капибары с прерываемой
          интерполяцией каналов (без телепортации при смене статуса в реальном времени) и адаптацией
          под <code>prefers-reduced-motion</code>.
        </p>
      </div>
    </BaseCard>

    <div class="flex flex-col gap-4">
      <BaseCard
        variant="verdict-safe"
        padding="md"
        class="flex flex-col gap-4 sm:flex-row sm:items-start"
      >
        <div
          class="border-border bg-surface shadow-card h-20 w-20 shrink-0 overflow-hidden rounded-md border p-1"
        >
          <CapyMascot verdict="green" size="compact" />
        </div>
        <div class="flex flex-1 flex-col gap-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-text-primary text-[16px] font-semibold">Вердикт Юдзу: Чистый лот</h3>
              <BaseBadge variant="success">
                <template #icon>
                  <ShieldCheck :size="14" :stroke-width="2" />
                </template>
                Одобрено к покупке
              </BaseBadge>
            </div>
            <span class="text-success text-[13px] font-semibold">Выгода +415 101 ₽</span>
          </div>
          <p class="text-text-secondary text-[14px] leading-relaxed">
            Заводской окрас металлических элементов, силовая структура не нарушена, подтверждённый
            пробег 58 240 км. Контрактная дверь доступна во Владивостоке в заводской цвет.
          </p>
        </div>
      </BaseCard>

      <BaseCard
        variant="verdict-warning"
        padding="md"
        class="flex flex-col gap-4 sm:flex-row sm:items-start"
      >
        <div
          class="border-border bg-surface shadow-card h-20 w-20 shrink-0 overflow-hidden rounded-md border p-1"
        >
          <CapyMascot verdict="yellow" size="compact" />
        </div>
        <div class="flex flex-1 flex-col gap-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-text-primary text-[16px] font-semibold">
                Вердикт Юдзу: Внимание к смете
              </h3>
              <BaseBadge variant="warning">
                <template #icon>
                  <AlertTriangle :size="14" :stroke-width="2" />
                </template>
                Умеренная выгода
              </BaseBadge>
            </div>
            <span class="text-warning text-[13px] font-semibold">Выгода +92 000 ₽ • Окрас W2</span>
          </div>
          <p class="text-text-secondary text-[14px] leading-relaxed">
            Геометрия кузова цела, но требуется вторичный окрас двух элементов и подбор редкого
            трёхслойного перламутра на СТО Владивостока. Проверьте вкладку «Техника».
          </p>
        </div>
      </BaseCard>

      <BaseCard
        variant="verdict-danger"
        padding="md"
        class="flex flex-col gap-4 sm:flex-row sm:items-start"
      >
        <div
          class="border-border bg-surface shadow-card h-20 w-20 shrink-0 overflow-hidden rounded-md border p-1"
        >
          <CapyMascot verdict="red" size="compact" />
        </div>
        <div class="flex flex-1 flex-col gap-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-text-primary text-[16px] font-semibold">Вердикт Юдзу: Стоп-фактор</h3>
              <BaseBadge variant="danger">
                <template #icon>
                  <CircleAlert :size="14" :stroke-width="2" />
                </template>
                Не рекомендую
              </BaseBadge>
            </div>
            <span class="text-danger text-[13px] font-semibold">Оценка R • Скрытый ремонт</span>
          </div>
          <p class="text-text-secondary text-[14px] leading-relaxed">
            В истории торгов найден аварийный лот со следами вытяжки лонжерона. Риск коммерческого
            утильсбора и нерентабельного восстановления.
          </p>
        </div>
      </BaseCard>
    </div>
  </BaseCard>
</template>
