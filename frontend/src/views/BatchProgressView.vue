<script setup lang="ts">
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Clock,
  Loader2,
  OctagonAlert,
  Plus,
  RefreshCw,
} from '@lucide/vue'
import { useMediaQuery } from '@vueuse/core'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { BatchUploadSheet, LotPreviewSheets } from '@/components/lots'
import { CapyMascot } from '@/components/mascot'
import { BaseBadge, BaseButton, BaseCard, type BadgeVariant } from '@/components/ui'
import { useBatchesStore } from '@/stores/batches'
import type { BatchItemStatus, LotSummary, TrafficLightColor } from '@/types/api'
import { BATCH_MAX_FILES_PER_UPLOAD, BATCH_MAX_TOTAL_FILES } from '@/utils/batchFiles'
import { formatRub, formatTaskStepRu, formatVerdictLabelRu } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()
const batchesStore = useBatchesStore()
const isDesktop = useMediaQuery('(min-width: 768px)')

const isUploadOpen = ref(false)
const uploadMode = ref<'create' | 'append'>('append')
const previewLot = ref<LotSummary | null>(null)

let pollTimerId: number | null = null
let pollingEpoch = 0

const batchId = computed(() => {
  const raw = route.params.batchId
  return typeof raw === 'string' ? raw : Array.isArray(raw) ? (raw[0] ?? '') : ''
})

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

const VERDICT_BADGE_VARIANT: Record<TrafficLightColor, BadgeVariant> = {
  green: 'success',
  yellow: 'warning',
  red: 'danger',
}

function stopPolling(): void {
  pollingEpoch += 1
  if (pollTimerId !== null && typeof window !== 'undefined') {
    window.clearTimeout(pollTimerId)
    pollTimerId = null
  }
}

async function runPollCycle(targetBatchId: string, epoch: number, initial: boolean): Promise<void> {
  if (!targetBatchId || epoch !== pollingEpoch) return

  const result = await batchesStore.fetchBatch(targetBatchId, { silent: !initial })
  if (epoch !== pollingEpoch) return

  if (
    result &&
    (result.status === 'queued' || result.status === 'processing') &&
    typeof window !== 'undefined'
  ) {
    const interval = Math.max(800, batchesStore.pollIntervalMs || 1500)
    pollTimerId = window.setTimeout(() => {
      void runPollCycle(targetBatchId, epoch, false)
    }, interval)
  }
}

function startPolling(targetBatchId: string): void {
  stopPolling()
  if (!targetBatchId) return
  const epoch = pollingEpoch
  void runPollCycle(targetBatchId, epoch, true)
}

watch(
  batchId,
  (nextId) => {
    batchesStore.clearErrors()
    startPolling(nextId)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  stopPolling()
})

function goHome(): void {
  void router.push({ name: 'home' })
}

function openAppendModal(): void {
  batchesStore.clearErrors()
  uploadMode.value = 'append'
  isUploadOpen.value = true
}

function openCreateModal(): void {
  batchesStore.clearErrors()
  uploadMode.value = 'create'
  isUploadOpen.value = true
}

async function handleUploadSubmit(files: File[]): Promise<void> {
  if (uploadMode.value === 'append' && batchId.value) {
    const updated = await batchesStore.appendItems(batchId.value, files)
    isUploadOpen.value = false
    if (updated.status === 'queued' || updated.status === 'processing') {
      startPolling(batchId.value)
    }
    return
  }

  const created = await batchesStore.createBatch(files)
  isUploadOpen.value = false
  if (isDesktop.value) {
    goHome()
  } else {
    await router.push({ name: 'batch-progress', params: { batchId: created.batch_id } })
  }
}

function getItemTitle(item: BatchItemStatus): string {
  if (item.summary) {
    return item.summary.year
      ? `${item.summary.make} ${item.summary.model} ${item.summary.year}`
      : `${item.summary.make} ${item.summary.model}`
  }
  return item.preview_title || item.original_filename
}

function getItemSubtitle(item: BatchItemStatus): string {
  if (item.summary) {
    return `${item.summary.auction_house} #${item.summary.lot_number} · Оценка ${item.summary.overall_grade}`
  }
  if (item.status === 'failed') {
    return item.error_message || 'Не удалось распознать лист'
  }
  const stepLabel = formatTaskStepRu(item.current_step)
  return item.preview_title ? `${stepLabel} · ${item.original_filename}` : stepLabel
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
            v-for="item in batch.items"
            :key="`${item.file_index}-${item.lot_id ?? item.original_filename}`"
          >
            <!-- Ready Lot Row -->
            <BaseCard
              v-if="item.status === 'ready' && item.summary"
              variant="surface"
              padding="none"
              interactive
              class="overflow-hidden"
            >
              <button
                type="button"
                class="flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-3.5 text-left outline-none focus:outline-none focus-visible:outline-none"
                @click="previewLot = item.summary"
              >
                <div class="flex min-w-0 items-center gap-3">
                  <span
                    class="bg-success-bg text-success flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
                  >
                    <CheckCircle2 :size="17" :stroke-width="2" />
                  </span>

                  <div class="min-w-0">
                    <div class="text-text-primary truncate text-[15px] font-semibold">
                      {{ getItemTitle(item) }}
                    </div>
                    <div class="text-text-secondary truncate text-[12px]">
                      {{ getItemSubtitle(item) }}
                    </div>
                  </div>
                </div>

                <div class="flex shrink-0 items-center gap-2.5">
                  <div class="text-right">
                    <div class="text-text-primary text-[14px] font-semibold tabular-nums">
                      {{ formatRub(item.summary.turnkey_cost_rub) }}
                    </div>
                    <BaseBadge
                      :variant="VERDICT_BADGE_VARIANT[item.summary.verdict]"
                      class="mt-0.5"
                    >
                      {{ formatVerdictLabelRu(item.summary.verdict) }}
                    </BaseBadge>
                  </div>

                  <ChevronRight :size="16" class="text-text-tertiary shrink-0" />
                </div>
              </button>
            </BaseCard>

            <!-- Failed Item Row -->
            <BaseCard v-else-if="item.status === 'failed'" variant="surface" padding="none">
              <div class="flex items-center justify-between gap-3 px-4 py-3.5">
                <div class="flex min-w-0 items-center gap-3">
                  <span
                    class="bg-danger-bg text-danger flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
                  >
                    <OctagonAlert :size="17" :stroke-width="2" />
                  </span>
                  <div class="min-w-0">
                    <div class="text-text-primary truncate text-[14px] font-semibold">
                      {{ getItemTitle(item) }}
                    </div>
                    <div class="text-danger truncate text-[12px]">
                      {{ getItemSubtitle(item) }}
                    </div>
                  </div>
                </div>

                <BaseBadge variant="danger">Ошибка</BaseBadge>
              </div>
            </BaseCard>

            <!-- Processing / Queued Item Row -->
            <BaseCard v-else variant="surface" padding="none">
              <div class="flex items-center justify-between gap-3 px-4 py-3.5">
                <div class="flex min-w-0 items-center gap-3">
                  <span
                    class="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
                    :class="
                      item.status === 'processing'
                        ? 'bg-info-bg text-info'
                        : 'bg-surface-inset text-text-secondary'
                    "
                  >
                    <Loader2
                      v-if="item.status === 'processing'"
                      :size="16"
                      :stroke-width="2"
                      class="animate-spin"
                    />
                    <Clock v-else :size="16" :stroke-width="2" />
                  </span>

                  <div class="min-w-0">
                    <div class="text-text-primary truncate text-[14px] font-semibold">
                      {{ getItemTitle(item) }}
                    </div>
                    <div class="text-text-secondary truncate text-[12px]">
                      {{ getItemSubtitle(item) }}
                    </div>
                  </div>
                </div>

                <BaseBadge :variant="item.status === 'processing' ? 'info' : 'neutral'">
                  {{ item.status === 'processing' ? 'Анализ' : 'В очереди' }}
                </BaseBadge>
              </div>
            </BaseCard>
          </li>
        </ul>
      </section>
    </main>

    <BatchUploadSheet
      v-model:open="isUploadOpen"
      :mode="uploadMode"
      :max-files="uploadMode === 'append' ? remainingAppendSlots : BATCH_MAX_FILES_PER_UPLOAD"
      :is-submitting="batchesStore.isUploading || batchesStore.isAppending"
      :server-error="batchesStore.uploadError"
      @submit="handleUploadSubmit"
    />

    <LotPreviewSheets v-model:lot="previewLot" />
  </div>
</template>
