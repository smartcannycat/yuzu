<script setup lang="ts">
import { CheckSquare, OctagonAlert, Plus, Trash2, Undo2, X } from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { AppHeader, ProfileSheet } from '@/components/layout'
import {
  BatchUploadSheet,
  InProgressAccordion,
  LotFilterSheet,
  LotsFeed,
  LotsToolbar,
  type LotFilterDraft,
} from '@/components/lots'
import { BaseButton } from '@/components/ui'
import { useAuthStore } from '@/stores/auth'
import { useBatchesStore } from '@/stores/batches'
import { useLotsStore } from '@/stores/lots'
import type { InProgressItemPreview, LotSummary, TrafficLightColor } from '@/types/api'

const HOME_IN_PROGRESS_POLL_MS = 2000
const IN_PROGRESS_AUTO_EXPAND_LIMIT = 4
const DELETE_UNDO_MS = 5000

const router = useRouter()
const authStore = useAuthStore()
const lotsStore = useLotsStore()
const batchesStore = useBatchesStore()
const isDesktop = useMediaQuery('(min-width: 768px)')

const isProfileOpen = ref(false)
const isFiltersOpen = ref(false)
const isUploadOpen = ref(false)
const isInProgressOpen = ref(false)

let backgroundPollTimerId: number | null = null
let backgroundPollEpoch = 0

function stopBackgroundSync(): void {
  backgroundPollEpoch += 1
  if (backgroundPollTimerId !== null && typeof window !== 'undefined') {
    window.clearTimeout(backgroundPollTimerId)
    backgroundPollTimerId = null
  }
}

function scheduleBackgroundSync(options: { force?: boolean } = {}): void {
  stopBackgroundSync()
  if (
    (!options.force && lotsStore.inProgress.total_processing_lots <= 0) ||
    typeof window === 'undefined'
  ) {
    return
  }

  const epoch = backgroundPollEpoch
  backgroundPollTimerId = window.setTimeout(async () => {
    if (epoch !== backgroundPollEpoch) return
    await lotsStore.refreshLotsSilently()
    if (epoch !== backgroundPollEpoch) return
    if (lotsStore.inProgress.total_processing_lots > 0) {
      scheduleBackgroundSync()
    }
  }, HOME_IN_PROGRESS_POLL_MS)
}

watch(
  () => lotsStore.inProgress.total_processing_lots,
  (count) => {
    if (count > 0) {
      if (backgroundPollTimerId === null) {
        scheduleBackgroundSync()
      }
    } else {
      stopBackgroundSync()
      isInProgressOpen.value = false
    }
  },
)

onMounted(async () => {
  if (!lotsStore.hasLoadedOnce) {
    await lotsStore.fetchLots()
  }
  if (lotsStore.inProgress.total_processing_lots > 0) {
    scheduleBackgroundSync()
  }
})

interface PendingDeleteState {
  lot: LotSummary
  timerId: number
}

const pendingDelete = ref<PendingDeleteState | null>(null)
const selectionMode = ref(false)
const selectedLotIds = ref<Set<string>>(new Set())
const isBulkDeleting = ref(false)
const lifecycleActionError = ref<string | null>(null)

const visibleItems = computed(() => {
  const hiddenId = pendingDelete.value?.lot.lot_id
  return hiddenId ? lotsStore.items.filter((item) => item.lot_id !== hiddenId) : lotsStore.items
})

const allVisibleSelected = computed(
  () =>
    visibleItems.value.length > 0 &&
    visibleItems.value.every((item) => selectedLotIds.value.has(item.lot_id)),
)

async function commitSingleDelete(lotId: string): Promise<void> {
  try {
    await lotsStore.deleteLot(lotId)
  } catch (err) {
    lifecycleActionError.value =
      err instanceof Error && err.message ? err.message : 'Не удалось удалить лот'
  }
}

async function flushPendingDelete(commit: boolean): Promise<void> {
  const current = pendingDelete.value
  if (!current) return
  window.clearTimeout(current.timerId)
  pendingDelete.value = null
  if (commit) {
    await commitSingleDelete(current.lot.lot_id)
  }
}

function handleUndoDelete(): void {
  const current = pendingDelete.value
  if (!current) return
  window.clearTimeout(current.timerId)
  pendingDelete.value = null
}

async function handleToggleArchiveLot(lot: LotSummary): Promise<void> {
  lifecycleActionError.value = null
  try {
    await lotsStore.setLotArchived(lot.lot_id, !lot.is_archived)
  } catch (err) {
    lifecycleActionError.value =
      err instanceof Error && err.message ? err.message : 'Не удалось обновить статус лота'
  }
}

async function handleDeleteLot(lot: LotSummary): Promise<void> {
  lifecycleActionError.value = null
  await flushPendingDelete(true)

  const timerId = window.setTimeout(() => {
    const current = pendingDelete.value
    if (current?.lot.lot_id !== lot.lot_id) return
    pendingDelete.value = null
    void commitSingleDelete(lot.lot_id)
  }, DELETE_UNDO_MS)

  pendingDelete.value = { lot, timerId }
}

function handleStartMultiSelect(lot: LotSummary): void {
  lifecycleActionError.value = null
  selectionMode.value = true
  selectedLotIds.value = new Set([lot.lot_id])
}

function handleToggleSelectLot(lotId: string): void {
  const next = new Set(selectedLotIds.value)
  if (next.has(lotId)) {
    next.delete(lotId)
  } else {
    next.add(lotId)
  }
  selectedLotIds.value = next
}

function handleToggleSelectAll(): void {
  if (allVisibleSelected.value) {
    selectedLotIds.value = new Set()
    return
  }
  selectedLotIds.value = new Set(visibleItems.value.map((item) => item.lot_id))
}

function cancelSelectionMode(): void {
  selectionMode.value = false
  selectedLotIds.value = new Set()
}

async function handleBulkDeleteSelected(): Promise<void> {
  const ids = Array.from(selectedLotIds.value)
  if (ids.length === 0 || isBulkDeleting.value) return

  lifecycleActionError.value = null
  await flushPendingDelete(true)
  isBulkDeleting.value = true
  try {
    await lotsStore.bulkDeleteLots(ids)
    cancelSelectionMode()
  } catch (err) {
    lifecycleActionError.value =
      err instanceof Error && err.message ? err.message : 'Не удалось удалить выбранные лоты'
  } finally {
    isBulkDeleting.value = false
  }
}

onBeforeUnmount(() => {
  stopBackgroundSync()
  if (pendingDelete.value) {
    const lotId = pendingDelete.value.lot.lot_id
    window.clearTimeout(pendingDelete.value.timerId)
    pendingDelete.value = null
    void lotsStore.deleteLot(lotId)
  }
})

function openUploadSheet(): void {
  batchesStore.clearErrors()
  isUploadOpen.value = true
}

async function handleUploadSubmit(files: File[]): Promise<void> {
  const created = await batchesStore.createBatch(files)
  isUploadOpen.value = false

  if (isDesktop.value) {
    const totalInProgress = lotsStore.inProgress.total_processing_lots
    const isBatchActive = created.status === 'queued' || created.status === 'processing'
    const effectiveTotal =
      totalInProgress > 0 ? totalInProgress : isBatchActive ? created.total_items : 0
    isInProgressOpen.value = effectiveTotal > 0 && effectiveTotal <= IN_PROGRESS_AUTO_EXPAND_LIMIT
    scheduleBackgroundSync({ force: created.total_items > 0 && isBatchActive })
  } else {
    await router.push({
      name: 'batch-progress',
      params: { batchId: created.batch_id },
    })
  }
}

function handleSelectInProgressItem(item: InProgressItemPreview): void {
  if (item.status === 'ready' && item.lot_id) {
    void router.push({
      name: 'lot-detail',
      params: { lotId: item.lot_id },
    })
    return
  }

  void router.push({
    name: 'batch-progress',
    params: { batchId: item.batch_id },
  })
}

function handleSelectLot(lot: LotSummary): void {
  void router.push({
    name: 'lot-detail',
    params: { lotId: lot.lot_id },
  })
}

async function handleSearch(query: string) {
  lotsStore.query = query
  await lotsStore.fetchLots()
}

async function handleToggleModel(modelName: string | null) {
  lotsStore.selectedModel =
    modelName === null || lotsStore.selectedModel === modelName ? null : modelName
  await lotsStore.fetchLots()
}

async function handleToggleVerdict(verdict: TrafficLightColor | null) {
  lotsStore.selectedVerdict =
    verdict === null || lotsStore.selectedVerdict === verdict ? null : verdict
  await lotsStore.fetchLots()
}

async function handleToggleAnomaly() {
  lotsStore.onlyAnomalies = !lotsStore.onlyAnomalies
  await lotsStore.fetchLots()
}

async function handlePreviewFilterSheet(draft: LotFilterDraft) {
  let modelForDraft: string | undefined
  if (lotsStore.selectedModel) {
    if (!draft.make || draft.make === lotsStore.selectedMake) {
      modelForDraft = lotsStore.selectedModel
    } else if (
      lotsStore.items.some(
        (item) => item.model === lotsStore.selectedModel && item.make === draft.make,
      )
    ) {
      modelForDraft = lotsStore.selectedModel
    }
  }

  return lotsStore.fetchFilterPreview({
    query: lotsStore.query.trim() || undefined,
    make: draft.make || undefined,
    model: modelForDraft,
    verdict: draft.verdict || undefined,
    has_anomaly: draft.onlyAnomalies ? true : undefined,
    lifecycle: draft.lifecycle,
  })
}

async function handleApplyFilterSheet(draft: LotFilterDraft) {
  cancelSelectionMode()
  if (draft.make && draft.make !== lotsStore.selectedMake && lotsStore.selectedModel) {
    const modelBelongsToMake = lotsStore.items.some(
      (item) => item.model === lotsStore.selectedModel && item.make === draft.make,
    )
    if (!modelBelongsToMake) {
      lotsStore.selectedModel = null
    }
  }
  lotsStore.selectedMake = draft.make
  lotsStore.selectedVerdict = draft.verdict
  lotsStore.onlyAnomalies = draft.onlyAnomalies
  lotsStore.sortBy = draft.sortBy
  lotsStore.sortOrder = draft.sortOrder
  lotsStore.lifecycle = draft.lifecycle
  await lotsStore.fetchLots()
}

async function handleResetAllFilters() {
  cancelSelectionMode()
  lotsStore.resetFilters()
  await lotsStore.fetchLots()
}

async function handleLogout(): Promise<void> {
  isProfileOpen.value = false
  stopBackgroundSync()
  await authStore.logout()
  await router.replace({ name: 'auth' })
}
</script>

<template>
  <div
    class="mx-auto flex min-h-dvh w-full max-w-[1200px] flex-col px-4 pt-5 pb-24 sm:px-6 sm:pt-6 sm:pb-12"
  >
    <AppHeader
      :initials="authStore.initials"
      :display-name="authStore.displayName"
      @open-profile="isProfileOpen = true"
    >
      <template #actions>
        <div class="hidden sm:block">
          <BaseButton variant="primary" size="md" pill @click="openUploadSheet">
            <template #icon-left>
              <Plus :size="17" :stroke-width="2.2" />
            </template>
            Загрузить листы
          </BaseButton>
        </div>
      </template>
    </AppHeader>

    <InProgressAccordion
      v-model:open="isInProgressOpen"
      class="mt-4 sm:mt-5"
      :summary="lotsStore.inProgress"
      @select-item="handleSelectInProgressItem"
    />

    <LotsToolbar
      class="mt-4 sm:mt-5"
      :query="lotsStore.query"
      :selected-model="lotsStore.selectedModel"
      :selected-verdict="lotsStore.selectedVerdict"
      :only-anomalies="lotsStore.onlyAnomalies"
      :active-filters-count="lotsStore.activeFiltersCount"
      :has-any-active-filter="lotsStore.hasAnyActiveFilter"
      :has-loaded-once="lotsStore.hasLoadedOnce"
      :available-filters="lotsStore.availableFilters"
      @search="handleSearch"
      @toggle-model="handleToggleModel"
      @toggle-verdict="handleToggleVerdict"
      @toggle-anomaly="handleToggleAnomaly"
      @open-filters="isFiltersOpen = true"
      @reset-filters="handleResetAllFilters"
    />

    <div
      v-if="lifecycleActionError"
      role="alert"
      class="bg-danger-subtle border-danger/25 text-danger mt-4 flex items-center justify-between gap-3 rounded-md border px-3.5 py-2.5 text-[13px] font-medium"
    >
      <div class="flex items-center gap-2">
        <OctagonAlert :size="16" class="shrink-0" />
        <span>{{ lifecycleActionError }}</span>
      </div>
      <button
        type="button"
        aria-label="Скрыть ошибку"
        class="text-danger/80 hover:text-danger shrink-0 cursor-pointer rounded-full p-1"
        @click="lifecycleActionError = null"
      >
        <X :size="15" />
      </button>
    </div>

    <LotsFeed
      class="mt-5 sm:mt-6"
      :items="visibleItems"
      :is-loading="lotsStore.isLoading"
      :is-loading-more="lotsStore.isLoadingMore"
      :has-loaded-once="lotsStore.hasLoadedOnce"
      :has-more="lotsStore.hasMore"
      :has-any-active-filter="lotsStore.hasAnyActiveFilter"
      :error-message="lotsStore.errorMessage"
      :lifecycle="lotsStore.lifecycle"
      :selection-mode="selectionMode"
      :selected-ids="selectedLotIds"
      @select-lot="handleSelectLot"
      @retry="lotsStore.fetchLots()"
      @reset-filters="handleResetAllFilters"
      @open-upload="openUploadSheet"
      @load-more="lotsStore.loadMore()"
      @toggle-archive="handleToggleArchiveLot"
      @delete-lot="handleDeleteLot"
      @start-multi-select="handleStartMultiSelect"
      @toggle-select="handleToggleSelectLot"
    />

    <button
      v-if="!selectionMode && !pendingDelete"
      type="button"
      aria-label="Загрузить аукционные листы"
      class="bg-accent text-text-on-accent hover:bg-accent-hover focus-visible:outline-accent fixed right-4 bottom-5 z-30 inline-flex h-12 cursor-pointer items-center gap-2 rounded-full px-5 text-[15px] font-semibold shadow-lg transition-transform duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 active:scale-95 sm:hidden"
      @click="openUploadSheet"
    >
      <Plus :size="18" :stroke-width="2.2" />
      <span>Загрузить</span>
    </button>

    <!-- Single-delete 5-second Undo Toast -->
    <div
      v-if="pendingDelete && !selectionMode"
      role="status"
      aria-live="polite"
      class="bg-text-primary text-surface fixed inset-x-4 bottom-5 z-40 mx-auto flex max-w-md items-center justify-between gap-3 rounded-full px-4 py-2.5 shadow-xl sm:inset-x-auto sm:left-1/2 sm:min-w-[360px] sm:-translate-x-1/2"
    >
      <span class="truncate text-[13px] font-medium">
        «{{ pendingDelete.lot.make }} {{ pendingDelete.lot.model }}» удалён
      </span>
      <button
        type="button"
        class="text-accent hover:text-accent/90 inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-semibold transition-colors"
        @click="handleUndoDelete"
      >
        <Undo2 :size="14" />
        <span>Отменить</span>
      </button>
    </div>

    <!-- Bulk Selection Floating Bar -->
    <div
      v-if="selectionMode"
      role="region"
      aria-label="Массовые действия с лотами"
      class="bg-surface border-border fixed inset-x-3 bottom-4 z-40 mx-auto flex max-w-2xl flex-wrap items-center justify-between gap-2 rounded-2xl border px-3.5 py-2.5 shadow-xl sm:inset-x-auto sm:bottom-5 sm:left-1/2 sm:w-full sm:-translate-x-1/2 sm:rounded-full sm:px-4"
    >
      <div class="flex items-center gap-2.5">
        <CheckSquare :size="16" class="text-accent shrink-0" />
        <span class="text-text-primary text-[13px] font-semibold tabular-nums">
          Выбрано: {{ selectedLotIds.size }}
        </span>
        <button
          type="button"
          class="text-accent hover:text-accent-hover cursor-pointer text-[13px] font-medium"
          @click="handleToggleSelectAll"
        >
          {{ allVisibleSelected ? 'Снять все' : 'Выбрать все' }}
        </button>
      </div>

      <div class="flex items-center gap-2">
        <BaseButton
          variant="ghost"
          size="sm"
          pill
          :disabled="isBulkDeleting"
          @click="cancelSelectionMode"
        >
          Отмена
        </BaseButton>
        <BaseButton
          variant="destructive"
          size="sm"
          pill
          :disabled="selectedLotIds.size === 0"
          :loading="isBulkDeleting"
          @click="handleBulkDeleteSelected"
        >
          <template #icon-left>
            <Trash2 :size="14" />
          </template>
          Удалить ({{ selectedLotIds.size }})
        </BaseButton>
      </div>
    </div>

    <LotFilterSheet
      v-model:open="isFiltersOpen"
      :available-filters="lotsStore.availableFilters"
      :make="lotsStore.selectedMake"
      :verdict="lotsStore.selectedVerdict"
      :only-anomalies="lotsStore.onlyAnomalies"
      :sort-by="lotsStore.sortBy"
      :sort-order="lotsStore.sortOrder"
      :lifecycle="lotsStore.lifecycle"
      :preview-filters="handlePreviewFilterSheet"
      @apply="handleApplyFilterSheet"
      @reset="handleResetAllFilters"
    />

    <BatchUploadSheet
      v-model:open="isUploadOpen"
      mode="create"
      :is-submitting="batchesStore.isUploading"
      :server-error="batchesStore.uploadError"
      @submit="handleUploadSubmit"
    />

    <ProfileSheet
      v-model:open="isProfileOpen"
      :name="authStore.user?.name"
      :email="authStore.user?.email"
      @logout="handleLogout"
    />
  </div>
</template>
