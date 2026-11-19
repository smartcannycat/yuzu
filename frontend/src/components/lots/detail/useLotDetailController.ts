import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { LotDetailSheetKind } from '@/components/lots/detail/LotDetailSheets.vue'
import { formatLotSpecsSubtitle } from '@/components/lots/detail/lotPresentation'
import { useLotDetailStore } from '@/stores/lotDetail'
import type { RecalculateRequest } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatArchiveBadgeLabelRu } from '@/utils/formatters'

export type LotDetailTab = 'general' | 'tech' | 'economics'

const VALID_TABS: readonly LotDetailTab[] = ['general', 'tech', 'economics']

export function parseLotTabQuery(raw: unknown): LotDetailTab {
  if (typeof raw === 'string' && VALID_TABS.includes(raw as LotDetailTab)) {
    return raw as LotDetailTab
  }
  return 'general'
}

export function parseLotIdParam(raw: unknown): string {
  if (typeof raw === 'string') return raw.trim()
  if (Array.isArray(raw) && typeof raw[0] === 'string') return raw[0].trim()
  return ''
}

export function hasInAppBackHistory(): boolean {
  if (typeof window === 'undefined') return false
  const state = window.history.state as { back?: unknown } | null
  return typeof state?.back === 'string' && state.back.trim().length > 0
}

export function useLotDetailController(activeSheet: Ref<LotDetailSheetKind>) {
  const route = useRoute()
  const router = useRouter()
  const lotsStore = useLotDetailStore()

  const lotId = computed(() => parseLotIdParam(route.params.lotId))
  const activeTab = ref<LotDetailTab>(parseLotTabQuery(route.query.tab))

  const isUpdatingLifecycle = ref(false)
  const isDeleteConfirmOpen = ref(false)
  const isDeletingLot = ref(false)
  const lifecycleError = ref<string | null>(null)

  const detail = computed(() => {
    if (!lotsStore.currentLotDetail || lotsStore.currentLotDetail.lot_id !== lotId.value) {
      return null
    }
    return lotsStore.currentLotDetail
  })

  const headerSubtitle = computed(() =>
    detail.value ? formatLotSpecsSubtitle(detail.value.passport) : '',
  )

  const archiveBadgeLabel = computed(() =>
    detail.value
      ? formatArchiveBadgeLabelRu(detail.value.is_archived, detail.value.archived_reason)
      : null,
  )

  watch(
    lotId,
    async (nextId) => {
      activeSheet.value = null
      lifecycleError.value = null
      isDeleteConfirmOpen.value = false
      if (!nextId) return
      try {
        await lotsStore.fetchLotDetail(nextId)
      } catch (err: unknown) {
        lifecycleError.value = getErrorMessage(err, 'Не удалось загрузить спецификацию лота')
      }
    },
    { immediate: true },
  )

  watch(
    () => route.query.tab,
    (nextQueryTab) => {
      const parsed = parseLotTabQuery(nextQueryTab)
      if (parsed !== activeTab.value) {
        activeTab.value = parsed
      }
    },
  )

  function setTab(nextTab: LotDetailTab): void {
    activeTab.value = nextTab
    const nextQuery = { ...route.query }
    if (nextTab === 'general') {
      delete nextQuery.tab
    } else {
      nextQuery.tab = nextTab
    }
    void router.replace({ query: nextQuery })
  }

  const currentTabModel = computed<LotDetailTab>({
    get: () => activeTab.value,
    set: (nextTab) => {
      setTab(nextTab)
    },
  })

  function goBack(): void {
    if (hasInAppBackHistory()) {
      router.back()
      return
    }
    void router.push({ name: 'home' })
  }

  function goHome(): void {
    void router.push({ name: 'home' })
  }

  function handleRetry(): void {
    if (!lotId.value) return
    void lotsStore.fetchLotDetail(lotId.value)
  }

  function handleRecalculate(payload: RecalculateRequest): void {
    if (!lotId.value) return
    void lotsStore.recalculateLot(lotId.value, payload)
  }

  function handleResetSimulation(): void {
    if (!lotId.value || lotsStore.isRecalculating) return
    void lotsStore.resetLotSimulation(lotId.value)
  }

  const baseDocumentTitle = typeof document !== 'undefined' ? document.title : ''

  const lotDocumentTitle = computed(() => {
    if (!detail.value) return baseDocumentTitle
    const { make, model, first_reg_year: year, frame_id: frameId } = detail.value.passport
    const titleParts = [make, model, year ? String(year) : null].filter(Boolean).join(' ')
    return frameId ? `${titleParts} (${frameId}) — YUZU` : `${titleParts} — YUZU`
  })

  watch(
    lotDocumentTitle,
    (nextTitle) => {
      if (typeof document !== 'undefined' && nextTitle) {
        document.title = nextTitle
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    if (typeof document !== 'undefined' && baseDocumentTitle) {
      document.title = baseDocumentTitle
    }
  })

  function handlePrintPdf(): void {
    if (typeof window === 'undefined') return
    if (typeof document !== 'undefined' && lotDocumentTitle.value) {
      document.title = lotDocumentTitle.value
    }
    window.print()
  }

  async function handleToggleArchive(): Promise<void> {
    if (!detail.value || isUpdatingLifecycle.value || isDeletingLot.value) return
    lifecycleError.value = null
    isUpdatingLifecycle.value = true
    try {
      await lotsStore.setLotArchived(detail.value.lot_id, !detail.value.is_archived)
    } catch (err: unknown) {
      lifecycleError.value = getErrorMessage(err, 'Не удалось обновить статус архива')
    } finally {
      isUpdatingLifecycle.value = false
    }
  }

  function handleOpenDeleteConfirm(): void {
    lifecycleError.value = null
    isDeleteConfirmOpen.value = true
  }

  async function handleConfirmDelete(): Promise<void> {
    if (!detail.value || isDeletingLot.value) return
    lifecycleError.value = null
    isDeletingLot.value = true
    try {
      await lotsStore.deleteLot(detail.value.lot_id)
      isDeleteConfirmOpen.value = false
      await router.replace({ name: 'home' })
    } catch (err: unknown) {
      lifecycleError.value = getErrorMessage(err, 'Не удалось удалить лот')
    } finally {
      isDeletingLot.value = false
    }
  }

  return {
    lotsStore,
    detail,
    activeTab,
    currentTabModel,
    headerSubtitle,
    archiveBadgeLabel,
    isUpdatingLifecycle,
    isDeleteConfirmOpen,
    isDeletingLot,
    lifecycleError,
    setTab,
    goBack,
    goHome,
    handleRetry,
    handleRecalculate,
    handleResetSimulation,
    handlePrintPdf,
    handleToggleArchive,
    handleOpenDeleteConfirm,
    handleConfirmDelete,
  }
}
