import type { LotFilterDraft } from '@/components/lots'
import type {
  AvailableFilters,
  LotListQueryParams,
  LotSummary,
  TrafficLightColor,
} from '@/types/api'

export interface HomeFeedFilterStore {
  query: string
  selectedMake: string | null
  selectedModel: string | null
  selectedVerdict: TrafficLightColor | null
  onlyAnomalies: boolean
  sortBy: LotFilterDraft['sortBy']
  sortOrder: LotFilterDraft['sortOrder']
  lifecycle: LotFilterDraft['lifecycle']
  items: LotSummary[]
  fetchLots: () => Promise<void>
  fetchFilterPreview: (overrides: Partial<LotListQueryParams>) => Promise<AvailableFilters | null>
  resetFilters: () => void
}

export function useHomeFeedFilters(
  store: HomeFeedFilterStore,
  runSafeFeedOperation: (action: () => Promise<unknown>, fallback: string) => Promise<void>,
  cancelSelectionMode: () => void,
) {
  async function handleSearch(query: string): Promise<void> {
    store.query = query
    await runSafeFeedOperation(() => store.fetchLots(), 'Не удалось выполнить поиск лотов.')
  }

  async function handleToggleModel(modelName: string | null): Promise<void> {
    store.selectedModel = modelName === null || store.selectedModel === modelName ? null : modelName
    await runSafeFeedOperation(() => store.fetchLots(), 'Не удалось обновить фильтр по модели.')
  }

  async function handleToggleVerdict(verdict: TrafficLightColor | null): Promise<void> {
    store.selectedVerdict = verdict === null || store.selectedVerdict === verdict ? null : verdict
    await runSafeFeedOperation(() => store.fetchLots(), 'Не удалось применить фильтр вердикта.')
  }

  async function handleToggleAnomaly(): Promise<void> {
    store.onlyAnomalies = !store.onlyAnomalies
    await runSafeFeedOperation(() => store.fetchLots(), 'Не удалось применить фильтр аномалий.')
  }

  async function handlePreviewFilterSheet(draft: LotFilterDraft) {
    let modelForDraft: string | undefined
    if (store.selectedModel) {
      if (!draft.make || draft.make === store.selectedMake) {
        modelForDraft = store.selectedModel
      } else if (
        store.items.some((item) => item.model === store.selectedModel && item.make === draft.make)
      ) {
        modelForDraft = store.selectedModel
      }
    }

    return store.fetchFilterPreview({
      query: store.query.trim() || undefined,
      make: draft.make || undefined,
      model: modelForDraft,
      verdict: draft.verdict || undefined,
      has_anomaly: draft.onlyAnomalies ? true : undefined,
      lifecycle: draft.lifecycle,
    })
  }

  async function handleApplyFilterSheet(draft: LotFilterDraft): Promise<void> {
    cancelSelectionMode()
    if (draft.make && draft.make !== store.selectedMake && store.selectedModel) {
      const modelBelongsToMake = store.items.some(
        (item) => item.model === store.selectedModel && item.make === draft.make,
      )
      if (!modelBelongsToMake) {
        store.selectedModel = null
      }
    }
    store.selectedMake = draft.make
    store.selectedVerdict = draft.verdict
    store.onlyAnomalies = draft.onlyAnomalies
    store.sortBy = draft.sortBy
    store.sortOrder = draft.sortOrder
    store.lifecycle = draft.lifecycle
    await runSafeFeedOperation(() => store.fetchLots(), 'Не удалось применить фильтры.')
  }

  async function handleResetAllFilters(): Promise<void> {
    cancelSelectionMode()
    store.resetFilters()
    await runSafeFeedOperation(() => store.fetchLots(), 'Не удалось сбросить фильтры.')
  }

  return {
    handleSearch,
    handleToggleModel,
    handleToggleVerdict,
    handleToggleAnomaly,
    handlePreviewFilterSheet,
    handleApplyFilterSheet,
    handleResetAllFilters,
  }
}
