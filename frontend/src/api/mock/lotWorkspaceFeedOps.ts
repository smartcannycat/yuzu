import { createMockProblem } from '@/api/mock/helpers'
import type { MockBatchRecord } from '@/api/mock/lotBatchTemplates'
import { applyLotExpiry } from '@/api/mock/lotLifecycle'
import type { LotBulkDeleteResponse, LotSummary, RecalculateResponse } from '@/types/api'

export interface WorkspaceRuntimeState {
  feedLots: LotSummary[]
  promotedLotIds: Set<string>
  deletedLotIds: Set<string>
  suppressedAutoArchiveIds: Set<string>
  batches: Map<string, MockBatchRecord>
  getSequenceCounter: () => number
  nextSequenceCounter: () => number
  saveWorkspace: () => void
  advanceAllBatches: (nowMs: number) => void
}

export function syncBatchItemTemplate(
  batches: Map<string, MockBatchRecord>,
  updated: LotSummary,
): void {
  for (const record of batches.values()) {
    for (const item of record.items) {
      if (item.lotId === updated.lot_id) {
        item.template = updated
      }
    }
  }
}

export function syncAutoArchiveFeed(
  feedLots: LotSummary[],
  nowMs: number,
  suppressedAutoArchiveIds: ReadonlySet<string>,
): boolean {
  let didMutate = false
  for (let i = 0; i < feedLots.length; i += 1) {
    const lot = feedLots[i]!
    const result = applyLotExpiry(lot, nowMs, suppressedAutoArchiveIds)
    if (result.didChange) {
      feedLots[i] = result.lot
      didMutate = true
    }
  }
  return didMutate
}

function throwLotNotFound(lotId: string, detail: string): never {
  throw createMockProblem({
    slug: 'lot-not-found',
    title: 'Лот не найден',
    status: 404,
    detail,
    instance: `/api/v1/lots/${lotId}`,
  })
}

function removeLotFromFeed(state: WorkspaceRuntimeState, lotId: string): boolean {
  const index = state.feedLots.findIndex((item) => item.lot_id === lotId)
  if (index === -1 || state.deletedLotIds.has(lotId)) return false
  state.feedLots.splice(index, 1)
  state.deletedLotIds.add(lotId)
  state.suppressedAutoArchiveIds.delete(lotId)
  return true
}

export function updateWorkspaceLotLifecycle(
  state: WorkspaceRuntimeState,
  lotId: string,
  isArchived: boolean,
): LotSummary {
  const nowMs = Date.now()
  state.advanceAllBatches(nowMs)

  const index = state.feedLots.findIndex((item) => item.lot_id === lotId)
  if (index === -1 || state.deletedLotIds.has(lotId)) {
    throwLotNotFound(lotId, 'Лот не найден или был удалён.')
  }

  const current = state.feedLots[index]!
  const updated: LotSummary = isArchived
    ? {
        ...current,
        is_archived: true,
        archived_at:
          current.is_archived && current.archived_at
            ? current.archived_at
            : new Date(nowMs).toISOString(),
        archived_reason:
          current.is_archived && current.archived_reason ? current.archived_reason : 'manual',
      }
    : {
        ...current,
        is_archived: false,
        archived_at: null,
        archived_reason: null,
        expires_at: null,
      }

  if (isArchived) state.suppressedAutoArchiveIds.delete(lotId)
  else state.suppressedAutoArchiveIds.add(lotId)

  state.feedLots[index] = updated
  syncBatchItemTemplate(state.batches, updated)
  state.saveWorkspace()
  return { ...updated }
}

export function updateWorkspaceLotEconomics(
  state: WorkspaceRuntimeState,
  lotId: string,
  response: RecalculateResponse,
): LotSummary | null {
  const index = state.feedLots.findIndex((item) => item.lot_id === lotId)
  if (index === -1 || state.deletedLotIds.has(lotId)) return null

  const current = state.feedLots[index]!
  const updated: LotSummary = {
    ...current,
    turnkey_cost_rub: response.turnkey_cost_rub,
    net_benefit_rub: response.net_benefit_rub,
    verdict: response.verdict.verdict,
    verdict_headline: response.verdict.short_verdict_label,
  }
  state.feedLots[index] = updated
  syncBatchItemTemplate(state.batches, updated)
  state.saveWorkspace()
  return { ...updated }
}

export function deleteWorkspaceLot(state: WorkspaceRuntimeState, lotId: string): void {
  state.advanceAllBatches(Date.now())
  if (!removeLotFromFeed(state, lotId)) {
    throwLotNotFound(lotId, 'Лот не найден или уже был удалён.')
  }
  state.saveWorkspace()
}

export function bulkDeleteWorkspaceLots(
  state: WorkspaceRuntimeState,
  lotIds: readonly string[],
): LotBulkDeleteResponse {
  state.advanceAllBatches(Date.now())
  const deletedIds: string[] = []
  const notFoundIds: string[] = []
  const seen = new Set<string>()

  for (const lotId of lotIds) {
    if (seen.has(lotId)) continue
    seen.add(lotId)
    if (!removeLotFromFeed(state, lotId)) {
      notFoundIds.push(lotId)
      continue
    }
    deletedIds.push(lotId)
  }

  if (deletedIds.length > 0) state.saveWorkspace()

  return {
    deleted_ids: deletedIds,
    not_found_ids: notFoundIds,
    deleted_count: deletedIds.length,
  }
}
