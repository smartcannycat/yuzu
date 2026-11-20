import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient } from '@/api'
import type { ApiClient } from '@/api/types'
import { useLotFeedStore } from '@/stores/lotFeed'
import { ApiError, type BatchCreateResponse, type BatchProgressResponse } from '@/types/api'
import { extractApiErrorMessage } from '@/utils/errors'
import { onSessionReset } from '@/utils/sessionEvents'

export const MIN_POLL_INTERVAL_MS = 800
export const MAX_POLL_INTERVAL_MS = 10_000
export const DEFAULT_POLL_INTERVAL_MS = 1500

export function clampPollIntervalMs(rawMs: unknown): number {
  if (typeof rawMs !== 'number' || !Number.isFinite(rawMs) || rawMs <= 0) {
    return DEFAULT_POLL_INTERVAL_MS
  }
  return Math.min(MAX_POLL_INTERVAL_MS, Math.max(MIN_POLL_INTERVAL_MS, Math.round(rawMs)))
}

export const useBatchesStore = defineStore('batches', () => {
  const activeBatch = ref<BatchProgressResponse | null>(null)
  const pollIntervalMs = ref(DEFAULT_POLL_INTERVAL_MS)

  const isUploading = ref(false)
  const isAppending = ref(false)
  const isLoadingBatch = ref(false)
  const uploadError = ref<string | null>(null)
  const batchError = ref<string | null>(null)
  const batchErrorStatus = ref<number | null>(null)

  let latestFetchRequestId = 0
  let latestAppendRequestId = 0
  let sessionEpoch = 0

  const isTerminal = computed(() => {
    const status = activeBatch.value?.status
    return status === 'completed' || status === 'partial_failed' || status === 'failed'
  })

  const canAppend = computed(() => {
    if (!activeBatch.value) return false
    const status = activeBatch.value.status
    return status === 'queued' || status === 'processing' || status === 'partial_failed'
  })

  async function createBatch(
    files: readonly File[],
    client: ApiClient = apiClient,
  ): Promise<BatchCreateResponse> {
    const epoch = sessionEpoch
    isUploading.value = true
    uploadError.value = null

    try {
      const response = await client.lots.createBatch(files)
      if (epoch !== sessionEpoch) return response

      pollIntervalMs.value = clampPollIntervalMs(response.poll_interval_ms)

      // Sync home in_progress banner immediately without flickering feed cards.
      await useLotFeedStore().refreshLotsSilently(client)
      return response
    } catch (error: unknown) {
      if (epoch === sessionEpoch) {
        uploadError.value = extractApiErrorMessage(error, 'Не удалось загрузить аукционные листы.')
      }
      throw error
    } finally {
      if (epoch === sessionEpoch) {
        isUploading.value = false
      }
    }
  }

  async function fetchBatch(
    batchId: string,
    options: { silent?: boolean } = {},
    client: ApiClient = apiClient,
  ): Promise<BatchProgressResponse | null> {
    const epoch = sessionEpoch
    const fetchRequestId = ++latestFetchRequestId
    const appendSeqAtStart = latestAppendRequestId

    if (activeBatch.value && activeBatch.value.batch_id !== batchId) {
      activeBatch.value = null
    }

    const previousReadyCount =
      activeBatch.value?.batch_id === batchId ? activeBatch.value.ready_count : 0
    const previousStatus = activeBatch.value?.batch_id === batchId ? activeBatch.value.status : null

    if (!options.silent) {
      isLoadingBatch.value = true
    }
    batchError.value = null
    batchErrorStatus.value = null

    try {
      const response = await client.lots.getBatch(batchId)
      if (
        epoch !== sessionEpoch ||
        fetchRequestId !== latestFetchRequestId ||
        appendSeqAtStart !== latestAppendRequestId
      ) {
        return null
      }

      activeBatch.value = response

      const completedNow =
        previousStatus !== response.status &&
        (response.status === 'completed' ||
          response.status === 'partial_failed' ||
          response.status === 'failed')

      if (response.ready_count > previousReadyCount || completedNow) {
        void useLotFeedStore().refreshLotsSilently(client)
      }

      return response
    } catch (error: unknown) {
      if (epoch !== sessionEpoch || fetchRequestId !== latestFetchRequestId) return null
      const status = error instanceof ApiError ? error.status : 0
      if (!options.silent || status === 401 || status === 403 || status === 404) {
        activeBatch.value = null
      }
      batchError.value = extractApiErrorMessage(
        error,
        'Не удалось получить статус очереди обработки.',
      )
      batchErrorStatus.value = status
      return null
    } finally {
      if (epoch === sessionEpoch && fetchRequestId === latestFetchRequestId && !options.silent) {
        isLoadingBatch.value = false
      }
    }
  }

  async function appendItems(
    batchId: string,
    files: readonly File[],
    client: ApiClient = apiClient,
  ): Promise<BatchProgressResponse> {
    const epoch = sessionEpoch
    const appendRequestId = ++latestAppendRequestId
    if (activeBatch.value && activeBatch.value.batch_id !== batchId) {
      activeBatch.value = null
    }

    isAppending.value = true
    uploadError.value = null

    try {
      const response = await client.lots.appendBatchItems(batchId, files)
      if (epoch !== sessionEpoch) return response

      if (appendRequestId === latestAppendRequestId) {
        latestFetchRequestId += 1
        activeBatch.value = response
      }
      await useLotFeedStore().refreshLotsSilently(client)
      return response
    } catch (error: unknown) {
      if (epoch === sessionEpoch) {
        uploadError.value = extractApiErrorMessage(
          error,
          'Не удалось догрузить листы в текущую очередь.',
        )
      }
      throw error
    } finally {
      if (epoch === sessionEpoch) {
        isAppending.value = false
      }
    }
  }

  function clearErrors(): void {
    uploadError.value = null
    batchError.value = null
    batchErrorStatus.value = null
  }

  function clear(): void {
    sessionEpoch += 1
    latestFetchRequestId += 1
    latestAppendRequestId += 1
    activeBatch.value = null
    pollIntervalMs.value = DEFAULT_POLL_INTERVAL_MS
    isUploading.value = false
    isAppending.value = false
    isLoadingBatch.value = false
    uploadError.value = null
    batchError.value = null
    batchErrorStatus.value = null
  }

  onSessionReset('batches', clear)

  return {
    activeBatch,
    pollIntervalMs,
    isUploading,
    isAppending,
    isLoadingBatch,
    uploadError,
    batchError,
    batchErrorStatus,
    isTerminal,
    canAppend,
    createBatch,
    fetchBatch,
    appendItems,
    clearErrors,
    clear,
  }
})
