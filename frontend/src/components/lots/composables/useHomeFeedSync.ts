import { onBeforeUnmount, onMounted, onScopeDispose, ref, watch } from 'vue'

const HOME_IN_PROGRESS_POLL_MS = 2000

export interface UseHomeFeedSyncOptions {
  hasLoadedOnce: () => boolean
  totalProcessingLots: () => number
  fetchLots: () => Promise<void>
  refreshLotsSilently: () => Promise<void>
  onQueueEmpty: () => void
}

/**
 * Coordinates initial home feed fetch and background polling for active batches,
 * guarding every async resumption against component unmount.
 */
export function useHomeFeedSync(options: UseHomeFeedSyncOptions) {
  const isUnmounted = ref(false)
  let backgroundPollTimerId: number | null = null
  let backgroundPollEpoch = 0

  function stopBackgroundSync(): void {
    backgroundPollEpoch += 1
    if (backgroundPollTimerId !== null && typeof window !== 'undefined') {
      window.clearTimeout(backgroundPollTimerId)
      backgroundPollTimerId = null
    }
  }

  function scheduleBackgroundSync(syncOptions: { force?: boolean } = {}): void {
    stopBackgroundSync()
    if (
      isUnmounted.value ||
      (!syncOptions.force && options.totalProcessingLots() <= 0) ||
      typeof window === 'undefined'
    ) {
      return
    }

    const epoch = backgroundPollEpoch
    backgroundPollTimerId = window.setTimeout(async () => {
      if (isUnmounted.value || epoch !== backgroundPollEpoch) return
      try {
        await options.refreshLotsSilently()
      } catch {
        // Background refreshes never overwrite visible feed items with error states.
      }
      if (isUnmounted.value || epoch !== backgroundPollEpoch) return
      if (options.totalProcessingLots() > 0) {
        scheduleBackgroundSync()
      }
    }, HOME_IN_PROGRESS_POLL_MS)
  }

  watch(options.totalProcessingLots, (count) => {
    if (isUnmounted.value) return
    if (count > 0) {
      if (backgroundPollTimerId === null) {
        scheduleBackgroundSync()
      }
    } else {
      stopBackgroundSync()
      options.onQueueEmpty()
    }
  })

  onMounted(async () => {
    if (!options.hasLoadedOnce()) {
      try {
        await options.fetchLots()
      } catch {
        // Store surfaces fetch errors in errorMessage.
      }
    }
    if (isUnmounted.value) return
    if (options.totalProcessingLots() > 0) {
      scheduleBackgroundSync()
    }
  })

  function dispose(): void {
    isUnmounted.value = true
    stopBackgroundSync()
  }

  onBeforeUnmount(dispose)
  onScopeDispose(dispose)

  return {
    isUnmounted,
    stopBackgroundSync,
    scheduleBackgroundSync,
  }
}
