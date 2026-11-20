<script setup lang="ts">
import { AlertCircle, ArrowLeft, Loader2, OctagonAlert, Plus, RefreshCw, X } from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { BatchUploadSheet } from '@/components/lots'
import BatchItemCard from '@/components/lots/BatchItemCard.vue'
import { useBatchPolling } from '@/components/lots/composables/useBatchPolling'
import { CapyMascot } from '@/components/mascot'
import { BaseButton, BaseCard } from '@/components/ui'
import { useBatchesStore } from '@/stores/batches'
import { BATCH_MAX_FILES_PER_UPLOAD, BATCH_MAX_TOTAL_FILES } from '@/utils/batchFiles'
import { extractApiErrorMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const batchesStore = useBatchesStore()
const isDesktop = useMediaQuery('(min-width: 768px)')

const isUploadOpen = ref(false)
const uploadMode = ref<'create' | 'append'>('append')
const uploadActionError = ref<string | null>(null)

const batchId = computed(() => {
  const raw = route.params.batchId
  return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : ''
})

const { isUnmounted, startPolling } = useBatchPolling(batchId, batchesStore)

const batch = computed(() => {
  if (!batchesStore.activeBatch || batchesStore.activeBatch.batch_id !== batchId.value) {
    return null
  }
  return batchesStore.activeBatch
})

const remainingAppendSlots = computed(() => {
  if (!batch.value) return BATCH_MAX_FILES_PER_UPLOAD
  const remainingTotal = Math.max(0, BATCH_MAX_TOTAL_FILES - batch.value.total_count)
  return Math.min(BATCH_MAX_FILES_PER_UPLOAD, remainingTotal)
})

const progressPct = computed(() => {
  if (!batch.value || batch.value.total_count <= 0) return 0
  return Math.round((batch.value.processed_count / batch.value.total_count) * 100)
})

const progressBarClass = computed(() => {
  if (!batch.value) return 'bg-accent'
  if (batch.value.status === 'completed') return 'bg-success'
  if (batch.value.status === 'partial_failed') return 'bg-warning'
  if (batch.value.status === 'failed') return 'bg-danger'
  return 'bg-accent'
})

const effectiveUploadError = computed(() => batchesStore.uploadError || uploadActionError.value)

function goHome(): void {
  void router.push({ name: 'home' })
}

function openLotDetail(lotId: string): void {
  void router.push({ name: 'lot-detail', params: { lotId } })
}

function openAppendModal(): void {
  batchesStore.clearErrors()
  uploadActionError.value = null
  uploadMode.value = 'append'
  isUploadOpen.value = true
}

function openCreateModal(): void {
  batchesStore.clearErrors()
  uploadActionError.value = null
  uploadMode.value = 'create'
  isUploadOpen.value = true
}

async function handleUploadSubmit(files: File[]): Promise<void> {
  uploadActionError.value = null
  try {
    if (uploadMode.value === 'append' && batchId.value) {
      const updated = await batchesStore.appendItems(batchId.value, files)
      if (isUnmounted.value) return
      isUploadOpen.value = false
      if (updated.status === 'queued' || updated.status === 'processing') {
        startPolling(batchId.value)
      }
      return
    }

    const created = await batchesStore.createBatch(files)
    if (isUnmounted.value) return
    isUploadOpen.value = false
    if (isDesktop.value) {
      goHome()
    } else {
      await router.push({ name: 'batch-progress', params: { batchId: created.batch_id } })
    }
  } catch (error: unknown) {
    if (isUnmounted.value) return
    const fallback =
      uploadMode.value === 'append'
        ? 'Не удалось догрузить листы в текущую очередь.'
        : 'Не удалось загрузить аукционные листы.'
    uploadActionError.value = extractApiErrorMessage(error, fallback)
  }
}
</script>

<template>
  <div class="mx-auto flex min-h-dvh w-full max-w-[760px] flex-col px-4 pt-4 pb-10 sm:px-6 sm:pt-6">
    <!-- Top Bar -->
    <header class="flex items-center">
      <button
        type="button"
        class="text-text-secondary hover:text-text-primary hover:bg-surface inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[14px] font-medium whitespace-nowrap transition-colors"
        @click="goHome"
      >
        <ArrowLeft :size="17" :stroke-width="2" />
        <span>На главную</span>
      </button>
    </header>

    <!-- Initial Loading State -->
    <div v-if="batchesStore.isLoadingBatch && !batch" class="mt-6 flex flex-col gap-3">
      <BaseCard variant="surface" padding="lg" class="flex flex-col items-center gap-3 py-10">
        <Loader2 :size="28" class="text-accent animate-spin" />
        <p class="text-text-secondary text-[14px]">Загружаем статус очереди...</p>
      </BaseCard>
    </div>

    <!-- Error State (Batch Not Found / Network failure without cached data) -->
    <div v-else-if="batchesStore.batchError && !batch" class="mt-6">
      <BaseCard variant="surface" padding="lg" class="flex flex-col items-center gap-4 text-center">
        <span
          class="bg-danger-bg text-danger flex h-12 w-12 items-center justify-center rounded-full"
        >
          <AlertCircle :size="24" :stroke-width="1.9" />
        </span>
        <div class="flex flex-col gap-1">
          <h2 class="text-text-primary text-[17px] font-semibold">Не удалось открыть очередь</h2>
          <p class="text-text-secondary text-[14px] leading-relaxed">
            {{ batchesStore.batchError }}
          </p>
        </div>
        <div class="flex flex-wrap items-center justify-center gap-2.5">
          <BaseButton variant="secondary" @click="startPolling(batchId)">
            <template #icon-left>
              <RefreshCw :size="15" />
            </template>
            Повторить
          </BaseButton>
          <BaseButton variant="primary" @click="goHome">На главную</BaseButton>
        </div>
      </BaseCard>
    </div>

    <!-- Live Batch View -->
    <main v-else-if="batch" class="mt-4 flex flex-1 flex-col gap-4 sm:mt-5">
      <!-- Mascot + Progress Hero Card -->
      <BaseCard variant="surface" padding="lg" class="flex flex-col items-center gap-4 text-center">
        <CapyMascot
          :mood="batch.mascot.mood"
          :batch-status="batch.status"
          :ready-count="batch.ready_count"
          :failed-count="batch.failed_count"
          :badge-text="batch.mascot.badge_text"
          hide-badge
          size="hero"
        />

        <div class="flex w-full max-w-[360px] flex-col gap-2">
          <p class="text-text-primary text-[17px] leading-snug font-semibold">
            {{ batch.mascot.phrase_ru }}
          </p>

          <div class="bg-surface-inset h-1.5 w-full overflow-hidden rounded-full">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="progressBarClass"
              :style="{ width: `${progressPct}%` }"
            />
          </div>

          <div
            v-if="!batchesStore.isTerminal || batch.failed_count > 0"
            class="text-text-secondary flex items-center justify-between text-[12px] tabular-nums"
          >
            <span v-if="!batchesStore.isTerminal">
              {{ batch.processed_count }} из {{ batch.total_count }}
            </span>
            <span
              v-if="batch.failed_count > 0"
              class="text-danger font-medium"
              :class="batchesStore.isTerminal ? 'mx-auto' : ''"
            >
              Ошибок: {{ batch.failed_count }}
            </span>
          </div>
        </div>

        <div class="flex w-full max-w-[360px] flex-row gap-2">
          <BaseButton
            v-if="batchesStore.canAppend && remainingAppendSlots > 0"
            variant="secondary"
            block
            @click="openAppendModal"
          >
            <template #icon-left>
              <Plus :size="16" :stroke-width="2.1" />
            </template>
            Догрузить ещё листы
          </BaseButton>

          <template v-else-if="batchesStore.isTerminal">
            <BaseButton variant="primary" class="min-w-0 flex-1 px-3 sm:px-4" @click="goHome">
              В ленту лотов
            </BaseButton>
            <BaseButton
              variant="secondary"
              class="min-w-0 flex-1 px-3 sm:px-4"
              @click="openCreateModal"
            >
              <template #icon-left>
                <Plus :size="16" :stroke-width="2.1" />
              </template>
              Новая пачка
            </BaseButton>
          </template>
        </div>
      </BaseCard>

      <!-- Inline upload failure alert when sheet is closed -->
      <div
        v-if="effectiveUploadError && !isUploadOpen"
        role="alert"
        class="bg-danger-subtle border-danger/25 text-danger flex items-center justify-between gap-3 rounded-md border px-3.5 py-2.5 text-[13px] font-medium"
      >
        <div class="flex items-center gap-2">
          <OctagonAlert :size="16" class="shrink-0" />
          <span>{{ effectiveUploadError }}</span>
        </div>
        <button
          type="button"
          aria-label="Скрыть ошибку"
          class="text-danger/80 hover:text-danger shrink-0 cursor-pointer rounded-full p-1"
          @click="
            () => {
              batchesStore.clearErrors()
              uploadActionError = null
            }
          "
        >
          <X :size="15" />
        </button>
      </div>

      <!-- Inline transient polling warning if connection drops temporarily -->
      <div
        v-if="batchesStore.batchError"
        role="status"
        class="bg-warning-bg text-warning flex items-center justify-between gap-3 rounded-md px-3.5 py-2.5 text-[13px]"
      >
        <span>{{ batchesStore.batchError }}</span>
        <button
          type="button"
          class="cursor-pointer font-semibold underline underline-offset-2"
          @click="startPolling(batchId)"
        >
          Обновить
        </button>
      </div>

      <!-- Queue Items List -->
      <section aria-label="Листы в очереди">
        <ul class="flex flex-col gap-2.5">
          <li
            v-for="(item, idx) in batch.items"
            :key="`${idx}:${item.file_index}-${item.lot_id ?? item.original_filename}`"
          >
            <BatchItemCard :item="item" @open-lot="openLotDetail" />
          </li>
        </ul>
      </section>
    </main>

    <BatchUploadSheet
      v-model:open="isUploadOpen"
      :mode="uploadMode"
      :max-files="uploadMode === 'append' ? remainingAppendSlots : BATCH_MAX_FILES_PER_UPLOAD"
      :is-submitting="batchesStore.isUploading || batchesStore.isAppending"
      :server-error="effectiveUploadError"
      @submit="handleUploadSubmit"
    />
  </div>
</template>
