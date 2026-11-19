import { createMockProblem, generateUuid } from '@/api/mock/helpers'
import {
  DAG_STEPS,
  ITEM_STAGGER_MS,
  SEEDED_BATCH_GRACE_MS,
  buildBatchProgressSnapshot,
  validateUploadFilesForMock,
} from '@/api/mock/lotBatchSimulation'
import {
  buildLotSummaryFromTemplate,
  pickTemplateForFilename,
  type MockBatchItemRecord,
} from '@/api/mock/lotBatchTemplates'
import { MOCK_IN_PROGRESS_SUMMARY } from '@/api/mock/lotsSeed'
import type { WorkspaceRuntimeState } from '@/api/mock/lotWorkspaceFeedOps'
import type { BatchCreateResponse, BatchProgressResponse } from '@/types/api'
import { BATCH_MAX_TOTAL_FILES } from '@/utils/batchFiles'

export function seedInitialInProgressBatch(state: WorkspaceRuntimeState): void {
  const seededBatchId = MOCK_IN_PROGRESS_SUMMARY.items[0]?.batch_id
  if (!seededBatchId) return

  const bootTimeMs = Date.now()
  const createdAtIso = new Date(bootTimeMs).toISOString()
  state.batches.set(seededBatchId, {
    batchId: seededBatchId,
    createdAtIso,
    items: MOCK_IN_PROGRESS_SUMMARY.items.map((seedItem, idx) => {
      const templateSeed = pickTemplateForFilename(seedItem.display_title, idx + 5)
      const stepIdx = Math.max(0, DAG_STEPS.indexOf(seedItem.current_step))
      const lotId = generateUuid()
      return {
        lotId,
        fileIndex: idx,
        originalFilename: `sheet_${templateSeed.lot_number}.jpg`,
        initialPreviewTitle: seedItem.display_title,
        enqueuedAtMs: bootTimeMs,
        startDelayMs: SEEDED_BATCH_GRACE_MS + idx * 1400,
        initialStepIndex: stepIdx,
        template: buildLotSummaryFromTemplate(
          templateSeed,
          lotId,
          state.nextSequenceCounter(),
          createdAtIso,
        ),
      }
    }),
  })
  state.saveWorkspace()
}

export function promoteReadyItems(
  state: WorkspaceRuntimeState,
  progress: BatchProgressResponse,
): boolean {
  let didPromote = false
  for (const item of progress.items) {
    if (
      item.status === 'ready' &&
      item.summary &&
      !state.promotedLotIds.has(item.summary.lot_id) &&
      !state.deletedLotIds.has(item.summary.lot_id)
    ) {
      state.promotedLotIds.add(item.summary.lot_id)
      state.feedLots.unshift(item.summary)
      didPromote = true
    }
  }
  return didPromote
}

export function createWorkspaceBatch(
  state: WorkspaceRuntimeState,
  files: readonly File[],
): BatchCreateResponse {
  validateUploadFilesForMock(files, '/api/v1/lots/batches')
  const nowMs = Date.now()
  const createdAtIso = new Date(nowMs).toISOString()
  const batchId = generateUuid()

  const items: MockBatchItemRecord[] = files.map((file, idx) => {
    const lotId = generateUuid()
    const templateSeed = pickTemplateForFilename(file.name, idx + state.getSequenceCounter())
    return {
      lotId,
      fileIndex: idx,
      originalFilename: file.name,
      enqueuedAtMs: nowMs,
      startDelayMs: idx * ITEM_STAGGER_MS,
      initialStepIndex: 0,
      template: buildLotSummaryFromTemplate(
        templateSeed,
        lotId,
        state.nextSequenceCounter(),
        new Date(nowMs + idx * 1000).toISOString(),
      ),
    }
  })

  state.batches.set(batchId, { batchId, createdAtIso, items })
  state.saveWorkspace()

  return {
    batch_id: batchId,
    total_items: items.length,
    status: 'queued',
    created_at: createdAtIso,
    poll_interval_ms: 1500,
  }
}

export function getWorkspaceBatch(
  state: WorkspaceRuntimeState,
  batchId: string,
): BatchProgressResponse {
  const record = state.batches.get(batchId)
  if (!record) {
    throw createMockProblem({
      slug: 'batch-not-found',
      title: 'Очередь не найдена',
      status: 404,
      detail: `Пачка ${batchId} не найдена в очереди обработки.`,
      instance: `/api/v1/lots/batches/${batchId}`,
    })
  }
  const progress = buildBatchProgressSnapshot(record, Date.now(), state.deletedLotIds)
  if (promoteReadyItems(state, progress)) state.saveWorkspace()
  return progress
}

export function appendWorkspaceBatchItems(
  state: WorkspaceRuntimeState,
  batchId: string,
  files: readonly File[],
): BatchProgressResponse {
  const instancePath = `/api/v1/lots/batches/${batchId}/items`
  const record = state.batches.get(batchId)
  if (!record) {
    throw createMockProblem({
      slug: 'batch-not-found',
      title: 'Очередь не найдена',
      status: 404,
      detail: `Пачка ${batchId} не найдена в очереди обработки.`,
      instance: instancePath,
    })
  }

  const nowMs = Date.now()
  const currentProgress = buildBatchProgressSnapshot(record, nowMs, state.deletedLotIds)
  if (
    currentProgress.status === 'completed' ||
    currentProgress.status === 'partial_failed' ||
    currentProgress.status === 'failed'
  ) {
    throw createMockProblem({
      slug: 'batch-already-completed',
      title: 'Очередь уже завершена',
      status: 409,
      detail: 'Эта пачка уже завершена. Создайте новую загрузку с главного экрана.',
      instance: instancePath,
    })
  }

  validateUploadFilesForMock(files, instancePath)
  if (record.items.length + files.length > BATCH_MAX_TOTAL_FILES) {
    throw createMockProblem({
      slug: 'batch-total-limit-exceeded',
      title: 'Превышен общий лимит пачки',
      status: 400,
      detail: `В одной пачке может быть максимум ${BATCH_MAX_TOTAL_FILES} файлов.`,
      instance: instancePath,
    })
  }

  const startIndex = record.items.length
  for (const [offset, file] of files.entries()) {
    const lotId = generateUuid()
    const templateSeed = pickTemplateForFilename(
      file.name,
      startIndex + offset + state.getSequenceCounter(),
    )
    record.items.push({
      lotId,
      fileIndex: startIndex + offset,
      originalFilename: file.name,
      enqueuedAtMs: nowMs,
      startDelayMs: offset * ITEM_STAGGER_MS,
      initialStepIndex: 0,
      template: buildLotSummaryFromTemplate(
        templateSeed,
        lotId,
        state.nextSequenceCounter(),
        new Date(nowMs + offset * 1000).toISOString(),
      ),
    })
  }

  const updatedProgress = buildBatchProgressSnapshot(record, Date.now(), state.deletedLotIds)
  promoteReadyItems(state, updatedProgress)
  state.saveWorkspace()
  return updatedProgress
}
