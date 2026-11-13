import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { apiClient } from '@/api'
import type { ApiClient } from '@/api/types'
import { useLotsStore } from '@/stores/lots'
import { ApiError, type BatchCreateResponse, type BatchProgressResponse } from '@/types/api'

const DEFAULT_POLL_INTERVAL_MS = 1500

function formatBatchError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.detail
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export const useBatchesStore = defineStore('batches', () => {
  const activeBatch = ref<BatchProgressResponse | null>(null)
  const pollIntervalMs = ref(DEFAULT_POLL_INTERVAL_MS)

  const isUploading = ref(false)
  const isAppending = ref(false)
  const isLoadingBatch = ref(false)
  const uploadError = ref<string | null>(null)
  const batchError = ref<string | null>(null)

  let latestBatchRequestId = 0

  const isTerminal = computed(() => {
    const status = activeBatch.value?.status
    return status === 'completed' || status === 'partial_failed' || status === 'failed'
  })

  const canAppend = computed(() => {
    if (!activeBatch.value) return false
    return activeBatch.value.status === 'queued' || activeBatch.value.status === 'processing'
  })

  async function createBatch(
    files: readonly File[],
    client: ApiClient = apiClient,
  ): Promise<BatchCreateResponse> {
    isUploading.value = true
    uploadError.value = null

    try {
      const response = await client.lots.createBatch(files)
      pollIntervalMs.value =
        response.poll_interval_ms > 0 ? response.poll_interval_ms : DEFAULT_POLL_INTERVAL_MS

      // Sync home in_progress banner immediately without flickering feed cards.
      await useLotsStore().refreshLotsSilently(client)
      return response
    } catch (error: unknown) {
      const message = formatBatchError(error, 'Не удалось загрузить аукционные листы.')
      uploadError.value = message
      throw error
    } finally {
      isUploading.value = false
    }
  }

  async function fetchBatch(
    batchId: string,
    options: { silent?: boolean } = {},
    client: ApiClient = apiClient,
  ): Promise<BatchProgressResponse | null> {
    const requestId = ++latestBatchRequestId
    const previousReadyCount =
      activeBatch.value?.batch_id === batchId ? activeBatch.value.ready_count : 0
    const previousStatus = activeBatch.value?.batch_id === batchId ? activeBatch.value.status : null

    if (!options.silent) {
      isLoadingBatch.value = true
    }
    batchError.value = null

    try {
      const response = await client.lots.getBatch(batchId)
      if (requestId !== latestBatchRequestId) return null

      activeBatch.value = response

      const completedNow =
        previousStatus !== response.status &&
        (response.status === 'completed' ||
          response.status === 'partial_failed' ||
          response.status === 'failed')

      if (response.ready_count > previousReadyCount || completedNow) {
        void useLotsStore().refreshLotsSilently(client)
      }

      return response
    } catch (error: unknown) {
      if (requestId !== latestBatchRequestId) return null
      batchError.value = formatBatchError(error, 'Не удалось получить статус очереди обработки.')
      return null
    } finally {
      if (requestId === latestBatchRequestId && !options.silent) {
        isLoadingBatch.value = false
      }
    }
  }

  async function appendItems(
    batchId: string,
    files: readonly File[],
    client: ApiClient = apiClient,
  ): Promise<BatchProgressResponse> {
    const requestId = ++latestBatchRequestId
    isAppending.value = true
    uploadError.value = null

    try {
      const response = await client.lots.appendBatchItems(batchId, files)
      if (requestId === latestBatchRequestId) {
        activeBatch.value = response
      }
      await useLotsStore().refreshLotsSilently(client)
      return response
    } catch (error: unknown) {
      const message = formatBatchError(error, 'Не удалось догрузить листы в текущую очередь.')
      uploadError.value = message
      throw error
    } finally {
      isAppending.value = false
    }
  }

  function clearErrors(): void {
    uploadError.value = null
    batchError.value = null
  }

  function clear(): void {
    latestBatchRequestId += 1
    activeBatch.value = null
    pollIntervalMs.value = DEFAULT_POLL_INTERVAL_MS
    isUploading.value = false
    isAppending.value = false
    isLoadingBatch.value = false
    uploadError.value = null
    batchError.value = null
  }

  return {
    activeBatch,
    pollIntervalMs,
    isUploading,
    isAppending,
    isLoadingBatch,
    uploadError,
    batchError,
    isTerminal,
    canAppend,
    createBatch,
    fetchBatch,
    appendItems,
    clearErrors,
    clear,
  }
})
