import { onBeforeUnmount, onScopeDispose, ref, watch, type Ref } from 'vue'

import { clampPollIntervalMs } from '@/stores/batches'
import type { BatchProgressResponse } from '@/types/api'

const MAX_RETRY_BACKOFF_MS = 30_000

export interface UseBatchPollingStore {
  pollIntervalMs: number
  batchErrorStatus: number | null
  clearErrors: () => void
  fetchBatch: (
    batchId: string,
    options?: { silent?: boolean },
  ) => Promise<BatchProgressResponse | null>
}

export function isNonRetryablePollError(status: number | null): boolean {
  if (status === null) return false
  // 401/403/404 and permanent 4xx errors should stop polling immediately; 408/429/5xx/network(0) retry.
  return status >= 400 && status < 500 && status !== 408 && status !== 429
}

export function useBatchPolling(batchId: Ref<string>, store: UseBatchPollingStore) {
  const isUnmounted = ref(false)
  let pollTimerId: number | null = null
  let pollingEpoch = 0
  let consecutivePollFailures = 0

  function stopPolling(): void {
    pollingEpoch += 1
    consecutivePollFailures = 0
    if (pollTimerId !== null && typeof window !== 'undefined') {
      window.clearTimeout(pollTimerId)
      pollTimerId = null
    }
  }

  async function runPollCycle(
    targetBatchId: string,
    epoch: number,
    initial: boolean,
  ): Promise<void> {
    if (isUnmounted.value || !targetBatchId || epoch !== pollingEpoch) return

    let result: BatchProgressResponse | null = null
    try {
      result = await store.fetchBatch(targetBatchId, { silent: !initial })
    } catch {
      result = null
    }
    if (isUnmounted.value || epoch !== pollingEpoch) return

    if (result) {
      consecutivePollFailures = 0
      if (
        (result.status === 'queued' || result.status === 'processing') &&
        typeof window !== 'undefined'
      ) {
        const interval = clampPollIntervalMs(store.pollIntervalMs)
        pollTimerId = window.setTimeout(() => {
          void runPollCycle(targetBatchId, epoch, false)
        }, interval)
      }
      return
    }

    if (!isNonRetryablePollError(store.batchErrorStatus) && typeof window !== 'undefined') {
      consecutivePollFailures += 1
      const baseInterval = clampPollIntervalMs(store.pollIntervalMs)
      const backoffDelay = Math.min(
        MAX_RETRY_BACKOFF_MS,
        baseInterval * 2 ** Math.min(consecutivePollFailures - 1, 4),
      )
      pollTimerId = window.setTimeout(() => {
        void runPollCycle(targetBatchId, epoch, false)
      }, backoffDelay)
    }
  }

  function startPolling(targetBatchId: string): void {
    stopPolling()
    if (isUnmounted.value || !targetBatchId) return
    const epoch = pollingEpoch
    void runPollCycle(targetBatchId, epoch, true)
  }

  watch(
    batchId,
    (nextId) => {
      if (isUnmounted.value) return
      store.clearErrors()
      startPolling(nextId)
    },
    { immediate: true },
  )

  function dispose(): void {
    isUnmounted.value = true
    stopPolling()
  }

  onBeforeUnmount(dispose)
  onScopeDispose(dispose)

  return {
    isUnmounted,
    startPolling,
    stopPolling,
  }
}
