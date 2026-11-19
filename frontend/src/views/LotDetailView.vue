<script setup lang="ts">
import { OctagonAlert, X } from '@lucide/vue'
import { computed, ref } from 'vue'

import LotDeleteConfirmSheet from '@/components/lots/detail/LotDeleteConfirmSheet.vue'
import LotDetailSheets, {
  type LotDetailSheetKind,
} from '@/components/lots/detail/LotDetailSheets.vue'
import LotDetailTopBar from '@/components/lots/detail/LotDetailTopBar.vue'
import LotPrintReport from '@/components/lots/detail/LotPrintReport.vue'
import LotStickyDangerAlert from '@/components/lots/detail/LotStickyDangerAlert.vue'
import LotTabEconomics from '@/components/lots/detail/LotTabEconomics.vue'
import LotTabGeneral from '@/components/lots/detail/LotTabGeneral.vue'
import LotTabTech from '@/components/lots/detail/LotTabTech.vue'
import {
  useLotDetailController,
  type LotDetailTab,
} from '@/components/lots/detail/useLotDetailController'
import {
  BaseBadge,
  BaseButton,
  BaseCard,
  SegmentedControl,
  type SegmentOption,
} from '@/components/ui'

const activeSheet = ref<LotDetailSheetKind>(null)

const {
  lotsStore,
  detail,
  activeTab,
  currentTabModel,
  headerSubtitle,
  archiveBadgeLabel,
  isUpdatingLifecycle,
  isDeleteConfirmOpen,
  isDeletingLot,
  lifecycleError,
  setTab,
  goBack,
  goHome,
  handleRetry,
  handleRecalculate,
  handleResetSimulation,
  handlePrintPdf,
  handleToggleArchive,
  handleOpenDeleteConfirm,
  handleConfirmDelete,
} = useLotDetailController(activeSheet)

const tabOptions = computed<SegmentOption<LotDetailTab>[]>(() => [
  { value: 'general', label: 'Общий' },
  {
    value: 'tech',
    label: 'Техника',
    badge:
      detail.value && detail.value.passport.defects.length > 0
        ? detail.value.passport.defects.length
        : undefined,
  },
  { value: 'economics', label: 'Экономика' },
])
</script>

<template>
  <div>
    <div
      class="mx-auto flex min-h-dvh w-full max-w-[1120px] flex-col px-4 pt-4 pb-12 sm:px-6 sm:pt-6 print:hidden"
    >
      <LotDetailTopBar
        :has-detail="Boolean(detail)"
        :is-archived="Boolean(detail?.is_archived)"
        :is-simulation-modified="lotsStore.isSimulationModified"
        :is-recalculating="lotsStore.isRecalculating"
        :is-updating-lifecycle="isUpdatingLifecycle"
        :is-deleting-lot="isDeletingLot"
        @back="goBack"
        @reset-simulation="handleResetSimulation"
        @toggle-archive="handleToggleArchive"
        @open-delete="handleOpenDeleteConfirm"
        @print-pdf="handlePrintPdf"
      />

      <div
        v-if="lifecycleError && !isDeleteConfirmOpen"
        role="alert"
        class="bg-danger-subtle border-danger/25 text-danger mt-3 flex items-center justify-between gap-3 rounded-md border px-3.5 py-2.5 text-[13px] font-medium"
      >
        <div class="flex items-center gap-2">
          <OctagonAlert :size="16" class="shrink-0" />
          <span>{{ lifecycleError }}</span>
        </div>
        <button
          type="button"
          aria-label="Скрыть ошибку"
          class="text-danger/80 hover:text-danger shrink-0 cursor-pointer rounded-full p-1"
          @click="lifecycleError = null"
        >
          <X :size="15" />
        </button>
      </div>

      <!-- Initial Loading Skeleton -->
      <div v-if="lotsStore.isLoadingDetail && !detail" class="mt-4 flex flex-col gap-4">
        <div class="bg-surface border-border h-24 animate-pulse rounded-md border" />
        <div
          class="bg-surface border-border h-11 w-full max-w-[420px] animate-pulse rounded-full border"
        />
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div
            class="bg-surface border-border h-72 animate-pulse rounded-md border lg:col-span-7"
          />
          <div
            class="bg-surface border-border h-72 animate-pulse rounded-md border lg:col-span-5"
          />
        </div>
      </div>

      <!-- Error / Not Found State -->
      <BaseCard
        v-else-if="lotsStore.detailError && !detail"
        variant="surface"
        padding="lg"
        class="mt-6 flex flex-col items-center gap-3 py-10 text-center"
      >
        <span
          class="bg-danger-bg text-danger flex h-11 w-11 items-center justify-center rounded-full"
        >
          <OctagonAlert :size="22" />
        </span>
        <div class="max-w-[420px]">
          <h1 class="text-text-primary text-[18px] font-semibold">
            {{ lotsStore.detailErrorStatus === 404 ? 'Лот не найден' : 'Не удалось загрузить лот' }}
          </h1>
          <p class="text-text-secondary mt-1 text-[14px]">
            {{ lotsStore.detailError }}
          </p>
        </div>
        <div class="mt-2 flex flex-wrap justify-center gap-2.5">
          <BaseButton variant="primary" pill @click="goHome">К ленте лотов</BaseButton>
          <BaseButton
            v-if="lotsStore.detailErrorStatus !== 404"
            variant="secondary"
            pill
            @click="handleRetry"
          >
            Повторить
          </BaseButton>
        </div>
      </BaseCard>

      <!-- Loaded Detail Content -->
      <template v-else-if="detail">
        <div
          class="mt-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-5"
        >
          <div class="flex min-w-0 flex-col gap-1">
            <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
              <h1
                class="text-text-primary text-[24px] leading-tight font-semibold tracking-[-0.015em] sm:text-[28px]"
              >
                {{ detail.passport.make }} {{ detail.passport.model }}
              </h1>
              <span v-if="detail.passport.trim" class="text-text-secondary text-[15px] font-medium">
                {{ detail.passport.trim }}
              </span>
              <BaseBadge
                v-if="archiveBadgeLabel"
                variant="neutral"
                size="sm"
                class="border-border bg-surface self-center border"
              >
                {{ archiveBadgeLabel }}
              </BaseBadge>
            </div>
            <p class="text-text-secondary text-[13px] sm:text-[14px]">
              {{ headerSubtitle }}
            </p>
          </div>

          <SegmentedControl
            v-model="currentTabModel"
            :options="tabOptions"
            ariaLabel="Разделы спецификации лота"
            full-width
            class="w-full shrink-0 md:w-[372px]"
          />
        </div>

        <LotStickyDangerAlert class="mt-4" :audit="detail.audit" @inspect="activeSheet = 'audit'" />

        <main class="mt-4 flex-1 sm:mt-5">
          <LotTabGeneral
            v-if="activeTab === 'general'"
            :detail="detail"
            :is-simulation-modified="lotsStore.isSimulationModified"
            @open-scan="activeSheet = 'scan'"
            @open-audit-history="activeSheet = 'audit'"
            @open-economics-tab="setTab('economics')"
          />

          <LotTabTech
            v-else-if="activeTab === 'tech'"
            :detail="detail"
            @open-repair="activeSheet = 'repair'"
            @open-inspector-notes="activeSheet = 'notes'"
            @open-safety-checklist="activeSheet = 'safety'"
          />

          <LotTabEconomics
            v-else
            :detail="detail"
            :is-recalculating="lotsStore.isRecalculating"
            :recalculate-error="lotsStore.recalculateError"
            :is-simulation-modified="lotsStore.isSimulationModified"
            @recalculate="handleRecalculate"
            @reset-simulation="handleResetSimulation"
          />
        </main>

        <LotDetailSheets v-model:active-sheet="activeSheet" :detail="detail" />

        <LotDeleteConfirmSheet
          v-model:open="isDeleteConfirmOpen"
          :make="detail.passport.make"
          :model="detail.passport.model"
          :is-deleting="isDeletingLot"
          :error-message="lifecycleError"
          @confirm="handleConfirmDelete"
        />
      </template>
    </div>

    <LotPrintReport
      v-if="detail"
      :detail="detail"
      :is-simulation-modified="lotsStore.isSimulationModified"
    />
  </div>
</template>
