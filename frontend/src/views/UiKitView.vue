<script setup lang="ts">
import {
  AlertTriangle,
  Anchor,
  ArrowLeft,
  Calculator,
  Check,
  CircleAlert,
  FileText,
  Fuel,
  Gauge,
  Info,
  Package,
  Scale,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
} from '@lucide/vue'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  BaseBadge,
  BaseButton,
  BaseCard,
  BaseInput,
  BaseSwitch,
  BottomSheet,
  BrandLogo,
  CapyMascot,
  CostLadder,
  InsetListGroup,
  InsetListItem,
  SegmentedControl,
  TtxGrid,
  type CapyState,
  type CostLadderStep,
  type SegmentOption,
  type TtxItem,
} from '@/components/ui'

const router = useRouter()

const isPersonalUtil = ref(true)
const isCalculating = ref(false)
const frameIdInput = ref('NRE210-2005418')
const searchInput = ref('')
const yearMonthInput = ref('2018/13')
const isSheetOpen = ref(false)
const activeSheetTopic = ref<'auction' | 'farpost'>('auction')
const demoMascotState = ref<CapyState>('sleeping')
const logoBoopCount = ref(0)

function handleLogoBoop(count: number): void {
  logoBoopCount.value = count
}

const mascotDemoOptions: Array<{
  state: CapyState
  label: string
  screen: string
  contract: string
  badge: string
}> = [
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

const activeMascotMeta = computed(
  () => mascotDemoOptions.find((o) => o.state === demoMascotState.value) ?? mascotDemoOptions[0]!,
)

type LotTab = 'general' | 'tech' | 'economics'
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
    hint: isPersonalUtil.value ? 'Льготный тариф (<= 160 л.с.)' : 'Коммерческий тариф ПП № 1255',
    value: isPersonalUtil.value ? '5 200 ₽' : '528 000 ₽',
  },
])

const totalTurnkey = computed(() => (isPersonalUtil.value ? '1 104 899 ₽' : '1 627 699 ₽'))

function triggerLoadingDemo() {
  if (isCalculating.value) return
  isCalculating.value = true
  window.setTimeout(() => {
    isCalculating.value = false
  }, 1200)
}

function openDetailsSheet(topic: 'auction' | 'farpost') {
  activeSheetTopic.value = topic
  isSheetOpen.value = true
}

function goHome() {
  void router.push({ name: 'home' })
}
</script>

<template>
  <div class="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-10">
    <!-- Top Header -->
    <header class="border-border flex flex-wrap items-center justify-between gap-4 border-b pb-5">
      <div class="flex flex-col gap-1">
        <div class="flex items-center gap-2">
          <BaseButton variant="ghost" size="sm" @click="goHome">
            <template #icon-left>
              <ArrowLeft :size="15" :stroke-width="2" />
            </template>
            Назад
          </BaseButton>
          <BaseBadge variant="info" size="sm">
            <template #icon>
              <Sparkles :size="12" :stroke-width="2" />
            </template>
            Clean Light v2.2
          </BaseBadge>
        </div>
        <h1 class="mt-1 text-[24px] leading-tight font-semibold tracking-[-0.015em] sm:text-[28px]">
          YUZU Component Library
        </h1>
        <p class="text-text-secondary text-[14px]">
          SF Pro Display • Lucide Icons • iOS 26 Switch • Bottom Sheet • WCAG AA & Adaptive
        </p>
      </div>

      <BaseButton variant="primary" size="md" @click="openDetailsSheet('auction')">
        <template #icon-left>
          <SlidersHorizontal :size="16" :stroke-width="2" />
        </template>
        Открыть Bottom Sheet
      </BaseButton>
    </header>

    <!-- Buttons -->
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
            @click="triggerLoadingDemo"
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

    <!-- Inputs, Switch iOS 26, Segmented Control -->
    <BaseCard as="section" padding="lg" class="flex flex-col gap-6">
      <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
        <h2 class="text-text-primary text-[17px] font-semibold">
          2. Поля ввода, свитч iOS 26 и Segmented Control
        </h2>
        <span class="text-text-secondary text-[12px]"
          >Клавиатурная навигация и 16px без зума iOS</span
        >
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
            :description="
              isPersonalUtil ? 'Льготный тариф 5 200 ₽' : 'Коммерческий тариф 528 000 ₽'
            "
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

    <!-- Status Badges -->
    <BaseCard as="section" padding="lg" class="flex flex-col gap-4">
      <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
        <h2 class="text-text-primary text-[17px] font-semibold">3. Статус-капсулы (Soft Tints)</h2>
        <span class="text-text-secondary text-[12px]"
          >Без обводки, иконки наследуют currentColor</span
        >
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

    <!-- Inset List -->
    <InsetListGroup title="4. Группированный список (Inset Grouped)">
      <InsetListItem
        title="Аукционный лист и перевод инспектора"
        subtitle="Нажмите, чтобы открыть Bottom Sheet"
        value="TAA Chubu #3142"
        squircle-color="#007AFF"
        interactive
        chevron
        @click="openDetailsSheet('auction')"
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
        @click="openDetailsSheet('farpost')"
      >
        <template #icon>
          <Package :size="16" :stroke-width="2" />
        </template>
      </InsetListItem>
    </InsetListGroup>

    <!-- TTX Grid & Cost Ladder -->
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <BaseCard as="section" padding="lg" class="flex flex-col gap-4">
        <div
          class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3"
        >
          <h2 class="text-text-primary text-[17px] font-semibold">5. Сетка ТТХ</h2>
          <span class="text-text-secondary text-[12px]">2 колонки без вертикальных рамок</span>
        </div>
        <TtxGrid :items="ttxItems" />
      </BaseCard>

      <BaseCard as="section" padding="lg" class="flex flex-col gap-4">
        <div
          class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3"
        >
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

    <!-- Verdict Cards with Mascot -->
    <BaseCard as="section" padding="lg" class="flex flex-col gap-5">
      <div class="border-border flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
        <h2 class="text-text-primary text-[17px] font-semibold">
          7. Живой маскот Юдзу («Дзен-Инспектор») и карточки вердикта
        </h2>
        <span class="text-text-secondary text-[12px]"
          >Единый SVG-риг • 6 состояний + Peeking • Duolingo Shape Language</span
        >
      </div>

      <!-- Interactive Hero Stage -->
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
            интерполяцией каналов (без телепортации при смене статуса в реальном времени) и
            адаптацией под <code>prefers-reduced-motion</code>.
          </p>
        </div>
      </BaseCard>

      <!-- Three Traffic Light Verdict Cards (Compact 80x80 Mode) -->
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
                <h3 class="text-text-primary text-[16px] font-semibold">
                  Вердикт Юдзу: Чистый лот
                </h3>
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
              <span class="text-warning text-[13px] font-semibold"
                >Выгода +92 000 ₽ • Окрас W2</span
              >
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
                <h3 class="text-text-primary text-[16px] font-semibold">
                  Вердикт Юдзу: Стоп-фактор
                </h3>
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

    <!-- 8. Brand Identity & Unified Logo Lockups -->
    <BaseCard as="section" padding="lg" class="flex flex-col gap-6">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <div class="flex flex-col gap-0.5">
          <h2 class="text-text-primary text-[19px] leading-snug font-semibold">
            8. Логотип и айдентика («YUZU Identity»)
          </h2>
          <span class="text-text-secondary text-[13px]">
            Живое дыхание, моргание и интерактивная реакция по клику на Капибару Юдзу («Boop»)
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <BaseBadge v-if="logoBoopCount > 0" variant="success" size="sm">
            Поглаживаний Юдзу: {{ logoBoopCount }}
          </BaseBadge>
          <span class="text-text-muted text-[12px]">Нажмите на капибару в любом логотипе ниже</span>
        </div>
      </div>

      <!-- Primary Two Variants Comparison: Mascot Lockup vs Wordmark Lockup -->
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BaseCard variant="inset" padding="md" class="flex flex-col justify-between gap-4">
          <div class="flex items-center justify-between gap-2">
            <span class="text-text-secondary text-[12px] font-medium">
              Вариант 1: С Капибарой Юдзу (<code>variant="mascot"</code>)
            </span>
            <BaseBadge variant="warning" size="sm">Основной • Интерактивный</BaseBadge>
          </div>
          <div class="border-border bg-surface flex flex-col gap-4 rounded-sm border p-4">
            <BrandLogo layout="auth" variant="mascot" @boop="handleLogoBoop" />
            <div class="border-border border-t pt-3">
              <BrandLogo layout="header" variant="mascot" @boop="handleLogoBoop" />
            </div>
          </div>
        </BaseCard>

        <BaseCard variant="inset" padding="md" class="flex flex-col justify-between gap-4">
          <div class="flex items-center justify-between gap-2">
            <span class="text-text-secondary text-[12px] font-medium">
              Вариант 2: Чистый текстовый (<code>variant="wordmark"</code>)
            </span>
            <BaseBadge variant="neutral" size="sm">Компактный</BaseBadge>
          </div>
          <div class="border-border bg-surface flex flex-col gap-4 rounded-sm border p-4">
            <BrandLogo layout="auth" variant="wordmark" />
            <div class="border-border border-t pt-3">
              <BrandLogo layout="header" variant="wordmark" />
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Capybara Mark Scale Showcase (no border stroke, no floor shadow) -->
      <BaseCard variant="inset" padding="md" class="flex flex-col gap-4">
        <div class="flex items-center justify-between gap-2">
          <div class="flex flex-col gap-0.5">
            <span class="text-text-primary text-[14px] font-semibold">
              Знак Капибары Юдзу по пропорциям рига (<code>layout="mark"</code>)
            </span>
            <span class="text-text-secondary text-[12px]">
              Точные пропорции спящей/выглядывающей капибары с юдзу на макушке (без рамки и тени)
            </span>
          </div>
          <BaseBadge variant="success" size="sm">SVG Rig 1:1</BaseBadge>
        </div>

        <div class="border-border bg-surface flex flex-wrap items-end gap-6 rounded-sm border p-5">
          <div class="flex flex-col items-center gap-1.5">
            <BrandLogo layout="mark" :size="28" @boop="handleLogoBoop" />
            <span class="text-text-muted font-mono text-[11px]">28px</span>
          </div>
          <div class="flex flex-col items-center gap-1.5">
            <BrandLogo layout="mark" :size="40" @boop="handleLogoBoop" />
            <span class="text-text-muted font-mono text-[11px]">40px</span>
          </div>
          <div class="flex flex-col items-center gap-1.5">
            <BrandLogo layout="mark" :size="54" @boop="handleLogoBoop" />
            <span class="text-text-muted font-mono text-[11px]">54px</span>
          </div>
          <div class="flex flex-col items-center gap-1.5">
            <BrandLogo layout="mark" :size="72" @boop="handleLogoBoop" />
            <span class="text-text-muted font-mono text-[11px]">72px</span>
          </div>
          <div class="flex flex-col items-center gap-1.5">
            <BrandLogo layout="mark" :size="96" @boop="handleLogoBoop" />
            <span class="text-text-muted font-mono text-[11px]">96px</span>
          </div>
        </div>
      </BaseCard>

      <!-- OpenGraph / Telegram Social Preview Card built with stageshow-vue -->
      <BaseCard variant="inset" padding="md" class="flex flex-col gap-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-col gap-0.5">
            <span class="text-text-primary text-[14px] font-semibold">
              OpenGraph-превью на базе <code>stageshow-vue</code> (<code>/og-image.png</code>,
              1200×630)
            </span>
            <span class="text-text-secondary text-[12px]">
              Продуктовый кадр с окном <code>yuzu.auto</code> и сателлитной карточкой вердикта Юдзу
            </span>
          </div>
          <BaseBadge variant="neutral" size="sm">1200×630 Stageshow</BaseBadge>
        </div>

        <div class="border-border bg-surface overflow-hidden rounded-md border">
          <img
            src="/og-image.png"
            alt="YUZU OpenGraph social preview card"
            width="1200"
            height="630"
            class="block h-auto w-full"
          />
        </div>
      </BaseCard>
    </BaseCard>

    <!-- Bottom Sheet Demo -->
    <BottomSheet
      v-model:open="isSheetOpen"
      :title="
        activeSheetTopic === 'auction' ? 'Замечания инспектора аукциона' : 'Смета ремонта (Farpost)'
      "
      :subtitle="
        activeSheetTopic === 'auction'
          ? 'TAA Chubu #3142 • Перевод с японского'
          : 'Контрактные детали во Владивостоке в заводской цвет'
      "
    >
      <div
        v-if="activeSheetTopic === 'auction'"
        class="text-text-primary flex flex-col gap-3 text-[14px] leading-relaxed"
      >
        <BaseCard variant="inset" padding="sm">
          <p class="text-text-primary font-medium">Перевод заметок инспектора</p>
          <p class="text-text-secondary mt-1">
            Руль слегка потёрт, лёгкое загрязнение салона, царапины на передней левой двери, следы
            подкраса на заднем бампере.
          </p>
        </BaseCard>
        <p class="text-text-secondary text-[13px]">
          Шторка поддерживает закрытие по Escape, клику на фон, свайпу за верхнюю планку на
          мобильных устройствах и ловушку фокуса для клавиатуры.
        </p>
      </div>

      <div v-else class="flex flex-col gap-3">
        <CostLadder
          :steps="[
            { label: 'Дверь передняя левая (в цвет 070)', value: 'от 18 000 ₽', active: true },
            { label: 'Снятие и монтаж детали', value: '5 000 ₽' },
            { label: 'Покраска (не требуется)', value: '0 ₽' },
            { label: 'PDR + полировка мелких сколов', value: '8 000 ₽' },
          ]"
          total-label="Итого расчётный ремонт"
          total-value="31 000 ₽"
        />
      </div>

      <template #footer>
        <BaseButton variant="primary" size="lg" block @click="isSheetOpen = false">
          Закрыть
        </BaseButton>
      </template>
    </BottomSheet>
  </div>
</template>
