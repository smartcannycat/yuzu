import { computed, onScopeDispose, ref, watch, type Ref } from 'vue'

import type { LotBulkDeleteResponse, LotSummary } from '@/types/api'
import { extractApiErrorMessage } from '@/utils/errors'

const DELETE_UNDO_MS = 5000

interface PendingDeleteState {
  lot: LotSummary
  timerId: number
}

export interface UseLotFeedActionsStore {
  items: LotSummary[]
  setLotArchived: (lotId: string, isArchived: boolean) => Promise<LotSummary>
  deleteLot: (lotId: string) => Promise<void>
  bulkDeleteLots: (lotIds: readonly string[]) => Promise<LotBulkDeleteResponse>
}

/**
 * Manages card lifecycle actions on the home feed: 5-second Undo toast for single deletes,
 * archive/unarchive mutations, and multi-select bulk deletion.
 */
export function useLotFeedActions(
  itemsSource: Ref<LotSummary[]>,
  store: Pick<UseLotFeedActionsStore, 'setLotArchived' | 'deleteLot' | 'bulkDeleteLots'>,
) {
  const pendingDelete = ref<PendingDeleteState | null>(null)
  const selectionMode = ref(false)
  const selectedLotIds = ref<Set<string>>(new Set())
  const isBulkDeleting = ref(false)
  const lifecycleActionError = ref<string | null>(null)

  let deleteOperationSeq = 0
  let isDisposed = false

  const visibleItems = computed(() => {
    const hiddenId = pendingDelete.value?.lot.lot_id
    return hiddenId
      ? itemsSource.value.filter((item) => item.lot_id !== hiddenId)
      : itemsSource.value
  })

  const allVisibleSelected = computed(
    () =>
      visibleItems.value.length > 0 &&
      visibleItems.value.every((item) => selectedLotIds.value.has(item.lot_id)),
  )

  watch(
    () => itemsSource.value,
    (nextItems) => {
      if (selectedLotIds.value.size === 0) return
      const validIds = new Set(nextItems.map((item) => item.lot_id))
      let changed = false
      const pruned = new Set<string>()
      for (const id of selectedLotIds.value) {
        if (validIds.has(id)) {
          pruned.add(id)
        } else {
          changed = true
        }
      }
      if (changed) {
        selectedLotIds.value = pruned
      }
    },
  )

  async function commitSingleDelete(lotId: string): Promise<void> {
    try {
      await store.deleteLot(lotId)
    } catch (err) {
      if (!isDisposed) {
        lifecycleActionError.value = extractApiErrorMessage(err, 'Не удалось удалить лот')
      }
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

  function flushPendingDeleteOnUnmount(): void {
    deleteOperationSeq += 1
    const current = pendingDelete.value
    if (!current) return
    window.clearTimeout(current.timerId)
    pendingDelete.value = null
    void commitSingleDelete(current.lot.lot_id)
  }

  onScopeDispose(() => {
    isDisposed = true
    flushPendingDeleteOnUnmount()
  })

  function handleUndoDelete(): void {
    deleteOperationSeq += 1
    const current = pendingDelete.value
    if (!current) return
    window.clearTimeout(current.timerId)
    pendingDelete.value = null
  }

  async function handleToggleArchiveLot(lot: LotSummary): Promise<void> {
    lifecycleActionError.value = null
    try {
      await store.setLotArchived(lot.lot_id, !lot.is_archived)
    } catch (err) {
      if (!isDisposed) {
        lifecycleActionError.value = extractApiErrorMessage(err, 'Не удалось обновить статус лота')
      }
    }
  }

  async function handleDeleteLot(lot: LotSummary): Promise<void> {
    const opSeq = ++deleteOperationSeq
    lifecycleActionError.value = null
    await flushPendingDelete(true)

    if (isDisposed || opSeq !== deleteOperationSeq) {
      return
    }

    const timerId = window.setTimeout(() => {
      const current = pendingDelete.value
      if (isDisposed || opSeq !== deleteOperationSeq || current?.lot.lot_id !== lot.lot_id) {
        return
      }
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

    deleteOperationSeq += 1
    lifecycleActionError.value = null
    await flushPendingDelete(true)
    if (isDisposed) return

    isBulkDeleting.value = true
    try {
      await store.bulkDeleteLots(ids)
      cancelSelectionMode()
    } catch (err) {
      if (!isDisposed) {
        lifecycleActionError.value = extractApiErrorMessage(
          err,
          'Не удалось удалить выбранные лоты',
        )
      }
    } finally {
      if (!isDisposed) {
        isBulkDeleting.value = false
      }
    }
  }

  return {
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
  }
}
