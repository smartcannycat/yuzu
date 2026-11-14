<script setup lang="ts">
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  OctagonAlert,
  Printer,
  RotateCcw,
  Trash2,
  X,
} from '@lucide/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import LotDetailSheets, {
  type LotDetailSheetKind,
} from '@/components/lots/detail/LotDetailSheets.vue'
import { formatLotSpecsSubtitle } from '@/components/lots/detail/lotPresentation'
import LotPrintReport from '@/components/lots/detail/LotPrintReport.vue'
import LotStickyDangerAlert from '@/components/lots/detail/LotStickyDangerAlert.vue'
import LotTabEconomics from '@/components/lots/detail/LotTabEconomics.vue'
import LotTabGeneral from '@/components/lots/detail/LotTabGeneral.vue'
import LotTabTech from '@/components/lots/detail/LotTabTech.vue'
import {
  BaseBadge,
  BaseButton,
  BaseCard,
  BottomSheet,
  SegmentedControl,
  type SegmentOption,
} from '@/components/ui'
import { useLotsStore } from '@/stores/lots'
import type { RecalculateRequest } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatArchiveBadgeLabelRu } from '@/utils/formatters'

type LotDetailTab = 'general' | 'tech' | 'economics'

const VALID_TABS: readonly LotDetailTab[] = ['general', 'tech', 'economics']

function parseTabQuery(raw: unknown): LotDetailTab {
  if (typeof raw === 'string' && VALID_TABS.includes(raw as LotDetailTab)) {
    return raw as LotDetailTab
  }
  return 'general'
}

function parseLotIdParam(raw: unknown): string {
  if (typeof raw === 'string') return raw.trim()
  if (Array.isArray(raw) && typeof raw[0] === 'string') return raw[0].trim()
  return ''
}

const route = useRoute()
const router = useRouter()
const lotsStore = useLotsStore()

const lotId = computed(() => parseLotIdParam(route.params.lotId))
const activeTab = ref<LotDetailTab>(parseTabQuery(route.query.tab))
const activeSheet = ref<LotDetailSheetKind>(null)

const detail = computed(() => {
  if (!lotsStore.currentLotDetail || lotsStore.currentLotDetail.lot_id !== lotId.value) {
    return null
  }
  return lotsStore.currentLotDetail
})

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

const headerSubtitle = computed(() => {
  if (!detail.value) return ''
  return formatLotSpecsSubtitle(detail.value.passport)
})

watch(
  lotId,
  async (nextId) => {
    activeSheet.value = null
    if (!nextId) return
    await lotsStore.fetchLotDetail(nextId)
  },
  { immediate: true },
)

watch(
  () => route.query.tab,
  (nextQueryTab) => {
    const parsed = parseTabQuery(nextQueryTab)
    if (parsed !== activeTab.value) {
      activeTab.value = parsed
    }
  },
)

function setTab(nextTab: LotDetailTab): void {
  activeTab.value = nextTab
  const nextQuery = { ...route.query }
  if (nextTab === 'general') {
    delete nextQuery.tab
  } else {
    nextQuery.tab = nextTab
  }
  void router.replace({ query: nextQuery })
}

const currentTabModel = computed<LotDetailTab>({
  get: () => activeTab.value,
  set: (nextTab) => {
    setTab(nextTab)
  },
})

function goBack(): void {
  if (typeof window !== 'undefined' && window.history.length > 1) {
    router.back()
    return
  }
  void router.push({ name: 'home' })
}

function handleRetry(): void {
  if (!lotId.value) return
  void lotsStore.fetchLotDetail(lotId.value)
}

function handleRecalculate(payload: RecalculateRequest): void {
  if (!lotId.value) return
  void lotsStore.recalculateLot(lotId.value, payload)
}

function handleResetSimulation(): void {
  if (!lotId.value) return
  void lotsStore.resetLotSimulation(lotId.value)
}

const baseDocumentTitle = typeof document !== 'undefined' ? document.title : ''

const lotDocumentTitle = computed(() => {
  if (!detail.value) return baseDocumentTitle
  const { make, model, first_reg_year: year, frame_id: frameId } = detail.value.passport
  const titleParts = [make, model, year ? String(year) : null].filter(Boolean).join(' ')
  return frameId ? `${titleParts} (${frameId}) — YUZU` : `${titleParts} — YUZU`
})

watch(
  lotDocumentTitle,
  (nextTitle) => {
    if (typeof document !== 'undefined' && nextTitle) {
      document.title = nextTitle
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document !== 'undefined' && baseDocumentTitle) {
    document.title = baseDocumentTitle
  }
})

function handlePrintPdf(): void {
  if (typeof window === 'undefined') return
  if (typeof document !== 'undefined' && lotDocumentTitle.value) {
    document.title = lotDocumentTitle.value
  }
  window.print()
}

const isUpdatingLifecycle = ref(false)
const isDeleteConfirmOpen = ref(false)
const isDeletingLot = ref(false)
const lifecycleError = ref<string | null>(null)

const archiveBadgeLabel = computed(() =>
  detail.value
    ? formatArchiveBadgeLabelRu(detail.value.is_archived, detail.value.archived_reason)
    : null,
)

watch(lotId, () => {
  lifecycleError.value = null
  isDeleteConfirmOpen.value = false
})

async function handleToggleArchive(): Promise<void> {
  if (!detail.value || isUpdatingLifecycle.value || isDeletingLot.value) return
  lifecycleError.value = null
  isUpdatingLifecycle.value = true
  try {
    await lotsStore.setLotArchived(detail.value.lot_id, !detail.value.is_archived)
  } catch (err) {
    lifecycleError.value = getErrorMessage(err, 'Не удалось обновить статус архива')
  } finally {
    isUpdatingLifecycle.value = false
  }
}

function handleOpenDeleteConfirm(): void {
  lifecycleError.value = null
  isDeleteConfirmOpen.value = true
}

async function handleConfirmDelete(): Promise<void> {
  if (!detail.value || isDeletingLot.value) return
  lifecycleError.value = null
  isDeletingLot.value = true
  try {
    await lotsStore.deleteLot(detail.value.lot_id)
    isDeleteConfirmOpen.value = false
    await router.replace({ name: 'home' })
  } catch (err) {
    lifecycleError.value = getErrorMessage(err, 'Не удалось удалить лот')
  } finally {
    isDeletingLot.value = false
  }
}
</script>

<template>
  <div>
    <div
      class="mx-auto flex min-h-dvh w-full max-w-[1120px] flex-col px-4 pt-4 pb-12 sm:px-6 sm:pt-6 print:hidden"
    >
      <!-- Top Bar -->
      <header class="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          class="text-text-secondary hover:text-text-primary hover:bg-surface inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[14px] font-medium whitespace-nowrap transition-colors"
          @click="goBack"
        >
          <ArrowLeft :size="17" :stroke-width="2" />
          <span>Назад</span>
        </button>

        <div v-if="detail" class="flex flex-wrap items-center gap-2">
          <BaseButton
            v-if="lotsStore.isSimulationModified"
            variant="ghost"
            size="sm"
            pill
            @click="handleResetSimulation"
          >
            <template #icon-left>
              <RotateCcw :size="14" />
            </template>
            Сбросить ставку
          </BaseButton>

          <BaseButton
            variant="secondary"
            size="sm"
            pill
            :loading="isUpdatingLifecycle"
            :disabled="isDeletingLot"
            @click="handleToggleArchive"
          >
            <template #icon-left>
              <ArchiveRestore v-if="detail.is_archived" :size="15" />
              <Archive v-else :size="15" />
            </template>
            {{ detail.is_archived ? 'Из архива' : 'В архив' }}
          </BaseButton>

          <BaseButton
            variant="secondary"
            size="sm"
            pill
            :disabled="isUpdatingLifecycle || isDeletingLot"
            class="!text-danger hover:!border-danger/30 hover:!bg-danger-subtle"
            @click="handleOpenDeleteConfirm"
          >
            <template #icon-left>
              <Trash2 :size="15" />
            </template>
            Удалить
          </BaseButton>

          <BaseButton variant="secondary" size="sm" pill @click="handlePrintPdf">
            <template #icon-left>
              <Printer :size="15" />
            </template>
            PDF
          </BaseButton>
        </div>
      </header>

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
          <BaseButton variant="primary" pill @click="router.push({ name: 'home' })">
            К ленте лотов
          </BaseButton>
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
        <!-- Lot Heading (Left) + 3-Tab Switcher (Right) -->
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

        <!-- Sticky Danger Alert (when critical anomaly detected) -->
        <LotStickyDangerAlert class="mt-4" :audit="detail.audit" @inspect="activeSheet = 'audit'" />

        <!-- Tab Panels -->
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

        <BottomSheet
          v-model:open="isDeleteConfirmOpen"
          title="Удалить лот?"
          max-width="sm"
          close-label="Отменить удаление"
          :persistent="isDeletingLot"
        >
          <div class="flex flex-col gap-4">
            <p class="text-text-secondary text-[14px] leading-relaxed">
              Лот «{{ detail.passport.make }} {{ detail.passport.model }}» будет убран из списка и
              фильтров.
            </p>

            <div
              v-if="lifecycleError"
              role="alert"
              class="bg-danger-subtle border-danger/25 text-danger flex items-center gap-2 rounded-md border px-3 py-2 text-[13px] font-medium"
            >
              <OctagonAlert :size="15" class="shrink-0" />
              <span>{{ lifecycleError }}</span>
            </div>

            <div class="flex items-center justify-end gap-2 pt-1">
              <BaseButton
                variant="secondary"
                size="md"
                pill
                :disabled="isDeletingLot"
                @click="isDeleteConfirmOpen = false"
              >
                Отмена
              </BaseButton>
              <BaseButton
                variant="destructive"
                size="md"
                pill
                :loading="isDeletingLot"
                @click="handleConfirmDelete"
              >
                <template #icon-left>
                  <Trash2 :size="15" />
                </template>
                Удалить лот
              </BaseButton>
            </div>
          </div>
        </BottomSheet>
      </template>
    </div>

    <!-- Print-only PDF Report -->
    <LotPrintReport
      v-if="detail"
      :detail="detail"
      :is-simulation-modified="lotsStore.isSimulationModified"
    />
  </div>
</template>
