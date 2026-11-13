<script setup lang="ts">
import { Plus } from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { AppHeader, ProfileSheet } from '@/components/layout'
import {
  BatchUploadSheet,
  InProgressAccordion,
  LotFilterSheet,
  LotPreviewSheets,
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

const router = useRouter()
const authStore = useAuthStore()
const lotsStore = useLotsStore()
const batchesStore = useBatchesStore()
const isDesktop = useMediaQuery('(min-width: 768px)')

const isProfileOpen = ref(false)
const isFiltersOpen = ref(false)
const isUploadOpen = ref(false)
const isInProgressOpen = ref(false)
const previewLot = ref<LotSummary | null>(null)

let backgroundPollTimerId: number | null = null
let backgroundPollEpoch = 0

function stopBackgroundSync(): void {
  backgroundPollEpoch += 1
  if (backgroundPollTimerId !== null && typeof window !== 'undefined') {
    window.clearTimeout(backgroundPollTimerId)
    backgroundPollTimerId = null
  }
}

function scheduleBackgroundSync(): void {
  stopBackgroundSync()
  if (lotsStore.inProgress.total_processing_lots <= 0 || typeof window === 'undefined') {
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

onBeforeUnmount(() => {
  stopBackgroundSync()
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
    isInProgressOpen.value = totalInProgress > 0 && totalInProgress <= IN_PROGRESS_AUTO_EXPAND_LIMIT
    scheduleBackgroundSync()
  } else {
    await router.push({
      name: 'batch-progress',
      params: { batchId: created.batch_id },
    })
  }
}

function handleSelectInProgressItem(item: InProgressItemPreview): void {
  void router.push({
    name: 'batch-progress',
    params: { batchId: item.batch_id },
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
  })
}

async function handleApplyFilterSheet(draft: LotFilterDraft) {
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
  await lotsStore.fetchLots()
}

async function handleResetAllFilters() {
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

    <LotsFeed
      class="mt-5 sm:mt-6"
      :items="lotsStore.items"
      :is-loading="lotsStore.isLoading"
      :is-loading-more="lotsStore.isLoadingMore"
      :has-loaded-once="lotsStore.hasLoadedOnce"
      :has-more="lotsStore.hasMore"
      :has-any-active-filter="lotsStore.hasAnyActiveFilter"
      :error-message="lotsStore.errorMessage"
      @select-lot="previewLot = $event"
      @retry="lotsStore.fetchLots()"
      @reset-filters="handleResetAllFilters"
      @open-upload="openUploadSheet"
      @load-more="lotsStore.loadMore()"
    />

    <button
      type="button"
      aria-label="Загрузить аукционные листы"
      class="bg-accent text-text-on-accent hover:bg-accent-hover focus-visible:outline-accent fixed right-4 bottom-5 z-30 inline-flex h-12 cursor-pointer items-center gap-2 rounded-full px-5 text-[15px] font-semibold shadow-lg transition-transform duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 active:scale-95 sm:hidden"
      @click="openUploadSheet"
    >
      <Plus :size="18" :stroke-width="2.2" />
      <span>Загрузить</span>
    </button>

    <LotFilterSheet
      v-model:open="isFiltersOpen"
      :available-filters="lotsStore.availableFilters"
      :make="lotsStore.selectedMake"
      :verdict="lotsStore.selectedVerdict"
      :only-anomalies="lotsStore.onlyAnomalies"
      :sort-by="lotsStore.sortBy"
      :sort-order="lotsStore.sortOrder"
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

    <LotPreviewSheets v-model:lot="previewLot" />

    <ProfileSheet
      v-model:open="isProfileOpen"
      :name="authStore.user?.name"
      :email="authStore.user?.email"
      @logout="handleLogout"
    />
  </div>
</template>
