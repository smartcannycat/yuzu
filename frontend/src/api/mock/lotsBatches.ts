import {
  buildBatchProgressSnapshot,
  validateUploadFilesForMock,
} from '@/api/mock/lotBatchSimulation'
import type { MockBatchRecord } from '@/api/mock/lotBatchTemplates'
import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import {
  appendWorkspaceBatchItems,
  createWorkspaceBatch,
  getWorkspaceBatch,
  promoteReadyItems,
  seedInitialInProgressBatch,
} from '@/api/mock/lotWorkspaceBatchOps'
import {
  bulkDeleteWorkspaceLots,
  deleteWorkspaceLot,
  syncAutoArchiveFeed,
  updateWorkspaceLotEconomics,
  updateWorkspaceLotLifecycle,
  type WorkspaceRuntimeState,
} from '@/api/mock/lotWorkspaceFeedOps'
import {
  MOCK_WORKSPACE_STORAGE_KEY,
  loadPersistedWorkspace,
  resetMockLotsWorkspace,
  savePersistedWorkspace,
} from '@/api/mock/lotWorkspaceStorage'
import type {
  BatchCreateResponse,
  BatchProgressResponse,
  InProgressItemPreview,
  InProgressSummary,
  LotBulkDeleteResponse,
  LotSummary,
  RecalculateResponse,
} from '@/types/api'

export { MOCK_WORKSPACE_STORAGE_KEY, resetMockLotsWorkspace, validateUploadFilesForMock }

export interface MockLotsWorkspace {
  getFeedSnapshot(): { lots: LotSummary[]; inProgress: InProgressSummary }
  updateLotLifecycle(lotId: string, isArchived: boolean): LotSummary
  updateLotEconomics(lotId: string, response: RecalculateResponse): LotSummary | null
  deleteLot(lotId: string): void
  bulkDeleteLots(lotIds: readonly string[]): LotBulkDeleteResponse
  createBatch(files: readonly File[]): BatchCreateResponse
  getBatch(batchId: string): BatchProgressResponse
  appendBatchItems(batchId: string, files: readonly File[]): BatchProgressResponse
}

export interface MockLotsWorkspaceOptions {
  persistState?: boolean
}

export function createMockLotsWorkspace(options: MockLotsWorkspaceOptions = {}): MockLotsWorkspace {
  const persistState = options.persistState ?? false
  const persisted = persistState ? loadPersistedWorkspace() : null

  const feedLots: LotSummary[] = persisted ? [...persisted.feedLots] : [...SEEDED_MOCK_LOTS]
  const promotedLotIds = new Set<string>(
    persisted ? persisted.promotedLotIds : feedLots.map((lot) => lot.lot_id),
  )
  const deletedLotIds = new Set<string>(persisted ? persisted.deletedLotIds : [])
  const suppressedAutoArchiveIds = new Set<string>(
    persisted ? persisted.suppressedAutoArchiveIds : [],
  )
  const batches = new Map<string, MockBatchRecord>(persisted ? persisted.batches : [])
  let sequenceCounter = persisted ? persisted.sequenceCounter : 10

  function saveWorkspace(): void {
    if (!persistState) return
    savePersistedWorkspace({
      feedLots,
      promotedLotIds: Array.from(promotedLotIds),
      deletedLotIds: Array.from(deletedLotIds),
      suppressedAutoArchiveIds: Array.from(suppressedAutoArchiveIds),
      batches: Array.from(batches.entries()),
      sequenceCounter,
    })
  }

  function advanceAllBatches(nowMs: number): InProgressSummary {
    let activeBatchesCount = 0
    const activeItems: InProgressItemPreview[] = []
    let didMutateFeed = syncAutoArchiveFeed(feedLots, nowMs, suppressedAutoArchiveIds)

    for (const record of batches.values()) {
      const progress = buildBatchProgressSnapshot(record, nowMs, deletedLotIds)
      if (promoteReadyItems(state, progress)) {
        didMutateFeed = true
      }
      const pending = progress.items.filter(
        (item) => item.status === 'queued' || item.status === 'processing',
      )
      if (pending.length > 0) {
        activeBatchesCount += 1
        for (const item of pending) {
          activeItems.push({
            batch_id: record.batchId,
            lot_id: item.lot_id,
            display_title: item.preview_title || item.original_filename,
            status: item.status,
            current_step: item.current_step,
          })
        }
      }
    }

    if (didMutateFeed) saveWorkspace()

    return {
      active_batches_count: activeBatchesCount,
      total_processing_lots: activeItems.length,
      items: activeItems,
    }
  }

  const state: WorkspaceRuntimeState = {
    feedLots,
    promotedLotIds,
    deletedLotIds,
    suppressedAutoArchiveIds,
    batches,
    getSequenceCounter: () => sequenceCounter,
    nextSequenceCounter: () => {
      sequenceCounter += 1
      return sequenceCounter
    },
    saveWorkspace,
    advanceAllBatches,
  }

  if (!persisted) {
    seedInitialInProgressBatch(state)
  }

  return {
    getFeedSnapshot() {
      const inProgress = advanceAllBatches(Date.now())
      return { lots: [...feedLots], inProgress }
    },
    updateLotLifecycle(lotId: string, isArchived: boolean): LotSummary {
      return updateWorkspaceLotLifecycle(state, lotId, isArchived)
    },
    updateLotEconomics(lotId: string, response: RecalculateResponse): LotSummary | null {
      return updateWorkspaceLotEconomics(state, lotId, response)
    },
    deleteLot(lotId: string): void {
      deleteWorkspaceLot(state, lotId)
    },
    bulkDeleteLots(lotIds: readonly string[]): LotBulkDeleteResponse {
      return bulkDeleteWorkspaceLots(state, lotIds)
    },
    createBatch(files: readonly File[]): BatchCreateResponse {
      return createWorkspaceBatch(state, files)
    },
    getBatch(batchId: string): BatchProgressResponse {
      return getWorkspaceBatch(state, batchId)
    },
    appendBatchItems(batchId: string, files: readonly File[]): BatchProgressResponse {
      return appendWorkspaceBatchItems(state, batchId, files)
    },
  }
}
