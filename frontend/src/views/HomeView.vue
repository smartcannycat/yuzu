<script setup lang="ts">
import { OctagonAlert, Plus, X } from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { computed, onBeforeUnmount, ref, toRef } from 'vue'
import { useRouter } from 'vue-router'

import { AppHeader, ProfileSheet } from '@/components/layout'
import {
  BatchUploadSheet,
  InProgressAccordion,
  LotFilterSheet,
  LotsFeed,
  LotsToolbar,
} from '@/components/lots'
import { useHomeFeedFilters } from '@/components/lots/composables/useHomeFeedFilters'
import { useHomeFeedSync } from '@/components/lots/composables/useHomeFeedSync'
import LotsBulkActionBar from '@/components/lots/LotsBulkActionBar.vue'
import { BaseButton } from '@/components/ui'
import { useLotFeedActions } from '@/composables/useLotFeedActions'
import { useAuthStore } from '@/stores/auth'
import { useBatchesStore } from '@/stores/batches'
import { useLotFeedStore } from '@/stores/lotFeed'
import type { InProgressItemPreview, LotSummary } from '@/types/api'
import { extractApiErrorMessage } from '@/utils/errors'

const IN_PROGRESS_AUTO_EXPAND_LIMIT = 4

const router = useRouter()
const authStore = useAuthStore()
const lotsStore = useLotFeedStore()
const batchesStore = useBatchesStore()
const isDesktop = useMediaQuery('(min-width: 768px)')

const isProfileOpen = ref(false)
const isFiltersOpen = ref(false)
const isUploadOpen = ref(false)
const isInProgressOpen = ref(false)
const uploadSubmitError = ref<string | null>(null)

const { isUnmounted, stopBackgroundSync, scheduleBackgroundSync } = useHomeFeedSync({
  hasLoadedOnce: () => lotsStore.hasLoadedOnce,
  totalProcessingLots: () => lotsStore.inProgress.total_processing_lots,
  fetchLots: () => lotsStore.fetchLots(),
  refreshLotsSilently: () => lotsStore.refreshLotsSilently(),
  onQueueEmpty: () => {
    isInProgressOpen.value = false
  },
})

const {
  pendingDelete,
  selectionMode,
  selectedLotIds,
  isBulkDeleting,
  lifecycleActionError,
  visibleItems,
  allVisibleSelected,
  flushPendingDeleteOnUnmount,
  handleUndoDelete,
  handleToggleArchiveLot,
  handleDeleteLot,
  handleStartMultiSelect,
  handleToggleSelectLot,
  handleToggleSelectAll,
  cancelSelectionMode,
  handleBulkDeleteSelected,
} = useLotFeedActions(toRef(lotsStore, 'items'), lotsStore)

onBeforeUnmount(() => {
  flushPendingDeleteOnUnmount()
})

const effectiveUploadError = computed(() => batchesStore.uploadError || uploadSubmitError.value)

async function runSafeFeedOperation(
  action: () => Promise<unknown>,
  fallback: string,
): Promise<void> {
  try {
    await action()
  } catch (error: unknown) {
    if (!isUnmounted.value) {
      lifecycleActionError.value = extractApiErrorMessage(error, fallback)
    }
  }
}

function openUploadSheet(): void {
  batchesStore.clearErrors()
  uploadSubmitError.value = null
  isUploadOpen.value = true
}

async function handleUploadSubmit(files: File[]): Promise<void> {
  uploadSubmitError.value = null
  try {
    const created = await batchesStore.createBatch(files)
    if (isUnmounted.value) return
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
  } catch (error: unknown) {
    if (isUnmounted.value) return
    const message = extractApiErrorMessage(error, 'Не удалось загрузить аукционные листы.')
    uploadSubmitError.value = message
    if (!isUploadOpen.value) {
      lifecycleActionError.value = message
    }
  }
}

function handleSelectInProgressItem(item: InProgressItemPreview): void {
  if (item.status === 'ready' && item.lot_id) {
    void router.push({ name: 'lot-detail', params: { lotId: item.lot_id } })
    return
  }
  void router.push({ name: 'batch-progress', params: { batchId: item.batch_id } })
}

function handleSelectLot(lot: LotSummary): void {
  void router.push({ name: 'lot-detail', params: { lotId: lot.lot_id } })
}

const {
  handleSearch,
  handleToggleModel,
  handleToggleVerdict,
  handleToggleAnomaly,
  handlePreviewFilterSheet,
  handleApplyFilterSheet,
  handleResetAllFilters,
} = useHomeFeedFilters(lotsStore, runSafeFeedOperation, cancelSelectionMode)

async function handleLogout(): Promise<void> {
  isProfileOpen.value = false
  stopBackgroundSync()
  try {
    await authStore.logout()
    await router.replace({ name: 'auth' })
  } catch (error: unknown) {
    if (!isUnmounted.value) {
      lifecycleActionError.value = extractApiErrorMessage(error, 'Не удалось выйти из аккаунта.')
    }
  }
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
      @retry="runSafeFeedOperation(() => lotsStore.fetchLots(), 'Не удалось загрузить лоты.')"
      @reset-filters="handleResetAllFilters"
      @open-upload="openUploadSheet"
      @load-more="
        runSafeFeedOperation(() => lotsStore.loadMore(), 'Не удалось загрузить следующую страницу.')
      "
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

    <LotsBulkActionBar
      :pending-delete-lot="pendingDelete?.lot ?? null"
      :selection-mode="selectionMode"
      :selected-count="selectedLotIds.size"
      :all-visible-selected="allVisibleSelected"
      :is-bulk-deleting="isBulkDeleting"
      @undo-delete="handleUndoDelete"
      @toggle-select-all="handleToggleSelectAll"
      @cancel-selection="cancelSelectionMode"
      @bulk-delete="handleBulkDeleteSelected"
    />

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
      :server-error="effectiveUploadError"
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
