import type { MockBatchRecord } from '@/api/mock/lotBatchTemplates'
import type { LotSummary } from '@/types/api'

export const MOCK_WORKSPACE_STORAGE_KEY = 'yuzu.mock.workspace.v2'

export interface PersistedWorkspaceState {
  feedLots: LotSummary[]
  promotedLotIds: string[]
  deletedLotIds: string[]
  suppressedAutoArchiveIds: string[]
  batches: Array<[string, MockBatchRecord]>
  sequenceCounter: number
}

function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function resetMockLotsWorkspace(): void {
  try {
    getStorage()?.removeItem(MOCK_WORKSPACE_STORAGE_KEY)
  } catch {
    // Ignore storage removal errors in restricted browser contexts.
  }
}

export function loadPersistedWorkspace(): PersistedWorkspaceState | null {
  try {
    const raw = getStorage()?.getItem(MOCK_WORKSPACE_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<PersistedWorkspaceState> | null
    if (
      !parsed ||
      !Array.isArray(parsed.feedLots) ||
      !Array.isArray(parsed.promotedLotIds) ||
      !Array.isArray(parsed.batches) ||
      typeof parsed.sequenceCounter !== 'number'
    ) {
      return null
    }
    return {
      feedLots: parsed.feedLots,
      promotedLotIds: parsed.promotedLotIds,
      deletedLotIds: Array.isArray(parsed.deletedLotIds) ? parsed.deletedLotIds : [],
      suppressedAutoArchiveIds: Array.isArray(parsed.suppressedAutoArchiveIds)
        ? parsed.suppressedAutoArchiveIds
        : [],
      batches: parsed.batches,
      sequenceCounter: parsed.sequenceCounter,
    }
  } catch {
    return null
  }
}

export function savePersistedWorkspace(payload: PersistedWorkspaceState): void {
  try {
    getStorage()?.setItem(MOCK_WORKSPACE_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Ignore storage quota / private-mode write failures cleanly.
  }
}
