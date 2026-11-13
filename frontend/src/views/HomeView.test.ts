import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useBatchesStore } from '@/stores/batches'
import { useLotsStore } from '@/stores/lots'
import type { BatchCreateResponse, InProgressItemPreview } from '@/types/api'
import HomeView from '@/views/HomeView.vue'

let uploadPayloadCount = 3

vi.mock('@/components/lots/BatchUploadSheet.vue', () => ({
  default: defineComponent({
    name: 'BatchUploadSheet',
    props: {
      open: { type: Boolean, default: false },
      isSubmitting: { type: Boolean, default: false },
      serverError: { type: String, default: null },
    },
    emits: ['update:open', 'submit'],
    setup(_props, { emit }) {
      return () =>
        h(
          'button',
          {
            type: 'button',
            'data-testid': 'mock-upload-submit',
            onClick: () => {
              const files = Array.from(
                { length: uploadPayloadCount },
                (_, index) => new File(['sheet'], `sheet_${index + 1}.jpg`, { type: 'image/jpeg' }),
              )
              emit('submit', files)
            },
          },
          'Submit',
        )
    },
  }),
}))

function makeInProgressItems(count: number): InProgressItemPreview[] {
  return Array.from({ length: count }, (_, index) => ({
    batch_id: 'batch-1',
    lot_id: `lot-${index + 1}`,
    display_title: `sheet_${index + 1}.jpg`,
    status: 'queued',
    current_step: 'gatekeeper',
  }))
}

function setDesktopMatchMedia(isDesktop: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('min-width') ? isDesktop : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('HomeView in-progress placement & auto-expand behavior', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    vi.useFakeTimers()
    uploadPayloadCount = 3
    setDesktopMatchMedia(true)
    pinia = createPinia()
    setActivePinia(pinia)
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  async function mountHomeView(initialProcessingCount: number) {
    const lotsStore = useLotsStore()
    lotsStore.hasLoadedOnce = true
    lotsStore.inProgress = {
      active_batches_count: initialProcessingCount > 0 ? 1 : 0,
      total_processing_lots: initialProcessingCount,
      items: makeInProgressItems(initialProcessingCount),
    }

    const batchesStore = useBatchesStore()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        { path: '/batches/:batchId', name: 'batch-progress', component: { template: '<div />' } },
        { path: '/auth', name: 'auth', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    await router.isReady()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(HomeView)
    app.use(pinia)
    app.use(router)
    app.mount(host)
    await flushUi()

    return { host, lotsStore, batchesStore, router }
  }

  it('renders InProgressAccordion above LotsToolbar and LotsFeed, starting collapsed on mount', async () => {
    const { host } = await mountHomeView(2)

    const inProgress = host.querySelector('section[aria-label="Автомобили в обработке"]')
    const toolbar = host.querySelector('section[aria-label="Поиск и фильтры лотов"]')
    const feed = host.querySelector('main')

    expect(inProgress).not.toBeNull()
    expect(toolbar).not.toBeNull()
    expect(feed).not.toBeNull()

    expect(
      inProgress!.compareDocumentPosition(toolbar!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(toolbar!.compareDocumentPosition(feed!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    const toggleButton = inProgress!.querySelector('button[aria-expanded]')
    expect(toggleButton?.getAttribute('aria-expanded')).toBe('false')
  })

  it('auto-expands on desktop upload when total processing lots <= 4 and collapses when > 4', async () => {
    const { host, lotsStore, batchesStore } = await mountHomeView(0)

    vi.spyOn(batchesStore, 'createBatch').mockImplementation(
      async (files): Promise<BatchCreateResponse> => {
        const nextCount = lotsStore.inProgress.total_processing_lots + files.length
        lotsStore.inProgress = {
          active_batches_count: 1,
          total_processing_lots: nextCount,
          items: makeInProgressItems(nextCount),
        }
        return {
          batch_id: 'batch-test',
          total_items: files.length,
          status: 'queued',
          created_at: '2026-11-13T00:00:00Z',
          poll_interval_ms: 1500,
        }
      },
    )

    const submitTrigger = host.querySelector(
      '[data-testid="mock-upload-submit"]',
    ) as HTMLButtonElement

    // Upload 4 items (<= 4) -> expanded
    uploadPayloadCount = 4
    submitTrigger.click()
    await flushUi()
    expect(
      host
        .querySelector('section[aria-label="Автомобили в обработке"] button[aria-expanded]')
        ?.getAttribute('aria-expanded'),
    ).toBe('true')

    // Upload 1 more (total 5 > 4) -> collapsed
    uploadPayloadCount = 1
    submitTrigger.click()
    await flushUi()
    expect(
      host
        .querySelector('section[aria-label="Автомобили в обработке"] button[aria-expanded]')
        ?.getAttribute('aria-expanded'),
    ).toBe('false')
  })

  it('falls back to created.total_items and forces background poll if initial refresh returned 0', async () => {
    const { host, lotsStore, batchesStore } = await mountHomeView(0)

    vi.spyOn(batchesStore, 'createBatch').mockResolvedValue({
      batch_id: 'batch-fallback',
      total_items: 3,
      status: 'queued',
      created_at: '2026-11-13T00:00:00Z',
      poll_interval_ms: 1500,
    })

    const refreshSpy = vi.spyOn(lotsStore, 'refreshLotsSilently').mockImplementation(async () => {
      lotsStore.inProgress = {
        active_batches_count: 1,
        total_processing_lots: 3,
        items: makeInProgressItems(3),
      }
    })

    const submitTrigger = host.querySelector(
      '[data-testid="mock-upload-submit"]',
    ) as HTMLButtonElement
    uploadPayloadCount = 3
    submitTrigger.click()
    await flushUi()

    await vi.advanceTimersByTimeAsync(2000)
    await flushUi()

    expect(refreshSpy).toHaveBeenCalled()
    expect(
      host
        .querySelector('section[aria-label="Автомобили в обработке"] button[aria-expanded]')
        ?.getAttribute('aria-expanded'),
    ).toBe('true')
  })

  it('resets accordion open state when total_processing_lots drops to 0', async () => {
    const { host, lotsStore, batchesStore } = await mountHomeView(0)

    vi.spyOn(batchesStore, 'createBatch').mockImplementation(
      async (files): Promise<BatchCreateResponse> => {
        lotsStore.inProgress = {
          active_batches_count: 1,
          total_processing_lots: files.length,
          items: makeInProgressItems(files.length),
        }
        return {
          batch_id: 'batch-reset',
          total_items: files.length,
          status: 'queued',
          created_at: '2026-11-13T00:00:00Z',
          poll_interval_ms: 1500,
        }
      },
    )

    const submitTrigger = host.querySelector(
      '[data-testid="mock-upload-submit"]',
    ) as HTMLButtonElement
    uploadPayloadCount = 2
    submitTrigger.click()
    await flushUi()

    expect(
      host
        .querySelector('section[aria-label="Автомобили в обработке"] button[aria-expanded]')
        ?.getAttribute('aria-expanded'),
    ).toBe('true')

    // Queue empties
    lotsStore.inProgress = { active_batches_count: 0, total_processing_lots: 0, items: [] }
    await flushUi()

    // Background item appears later without desktop upload -> starts collapsed
    lotsStore.inProgress = {
      active_batches_count: 1,
      total_processing_lots: 1,
      items: makeInProgressItems(1),
    }
    await flushUi()

    expect(
      host
        .querySelector('section[aria-label="Автомобили в обработке"] button[aria-expanded]')
        ?.getAttribute('aria-expanded'),
    ).toBe('false')
  })

  it('navigates to batch-progress on mobile upload', async () => {
    setDesktopMatchMedia(false)
    const { host, batchesStore, router } = await mountHomeView(0)
    const pushSpy = vi.spyOn(router, 'push')

    vi.spyOn(batchesStore, 'createBatch').mockResolvedValue({
      batch_id: 'batch-mobile-42',
      total_items: 2,
      status: 'queued',
      created_at: '2026-11-13T00:00:00Z',
      poll_interval_ms: 1500,
    })

    const submitTrigger = host.querySelector(
      '[data-testid="mock-upload-submit"]',
    ) as HTMLButtonElement
    uploadPayloadCount = 2
    submitTrigger.click()
    await flushUi()

    expect(pushSpy).toHaveBeenCalledWith({
      name: 'batch-progress',
      params: { batchId: 'batch-mobile-42' },
    })
  })

  it('supports card ··· menu (no chevron arrow), 5-sec Undo delete toast, and multi-select bulk delete', async () => {
    localStorage.clear()
    const { host, lotsStore } = await mountHomeView(0)
    const fetchPromise = lotsStore.fetchLots()
    await vi.advanceTimersByTimeAsync(400)
    await fetchPromise
    // Prevent background polling of batches left over by earlier tests in this file from injecting new lots mid-test
    vi.spyOn(lotsStore, 'refreshLotsSilently').mockResolvedValue()
    await flushUi()

    // ChevronRight arrow was removed from LotCard
    expect(host.querySelector('main article .lucide-chevron-right')).toBeNull()

    const initialCount = lotsStore.items.length
    expect(initialCount).toBeGreaterThanOrEqual(2)
    const firstLot = lotsStore.items[0]!
    const secondLot = lotsStore.items[1]!

    // Spy on deleteLot / bulkDeleteLots / setLotArchived
    const archiveSpy = vi.spyOn(lotsStore, 'setLotArchived').mockResolvedValue(firstLot)
    const deleteSpy = vi.spyOn(lotsStore, 'deleteLot').mockResolvedValue()
    const bulkDeleteSpy = vi.spyOn(lotsStore, 'bulkDeleteLots').mockResolvedValue({
      deleted_ids: [firstLot.lot_id, secondLot.lot_id],
      not_found_ids: [],
      deleted_count: 2,
    })

    // Open ··· menu on first card and click "В архив"
    const menuTriggers = Array.from(
      host.querySelectorAll('button[aria-label="Действия с лотом"]'),
    ) as HTMLButtonElement[]
    expect(menuTriggers.length).toBe(initialCount)

    menuTriggers[0]!.click()
    await flushUi()

    const archiveMenuItem = Array.from(host.querySelectorAll('[role="menuitem"]')).find((el) =>
      el.textContent?.includes('В архив'),
    ) as HTMLButtonElement | undefined
    expect(archiveMenuItem).toBeTruthy()
    archiveMenuItem!.click()
    await flushUi()
    expect(archiveSpy).toHaveBeenCalledWith(firstLot.lot_id, true)

    // Open ··· menu and click "Удалить" -> Undo toast appears, clicking "Отменить" cancels deletion
    menuTriggers[0]!.click()
    await flushUi()
    const deleteMenuItem = Array.from(host.querySelectorAll('[role="menuitem"]')).find((el) =>
      el.textContent?.includes('Удалить'),
    ) as HTMLButtonElement | undefined
    deleteMenuItem!.click()
    await flushUi()

    const toast = host.querySelector('[role="status"]')
    expect(toast?.textContent).toContain('удалён')
    expect(deleteSpy).not.toHaveBeenCalled()

    const undoButton = Array.from(toast?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Отменить'),
    ) as HTMLButtonElement | undefined
    expect(undoButton).toBeTruthy()
    undoButton!.click()
    await vi.advanceTimersByTimeAsync(5000)
    await flushUi()
    expect(deleteSpy).not.toHaveBeenCalled()

    // Delete again and let 5-second timer expire -> deleteLot is committed
    const freshTriggers = Array.from(
      host.querySelectorAll('button[aria-label="Действия с лотом"]'),
    ) as HTMLButtonElement[]
    freshTriggers[0]!.click()
    await flushUi()
    const deleteAgain = Array.from(host.querySelectorAll('[role="menuitem"]')).find((el) =>
      el.textContent?.includes('Удалить'),
    ) as HTMLButtonElement
    deleteAgain.click()
    await flushUi()

    await vi.advanceTimersByTimeAsync(5000)
    await flushUi()
    expect(deleteSpy).toHaveBeenCalledWith(firstLot.lot_id)

    // Enter multi-select via "Выбрать несколько" -> select 2nd lot -> bulk delete
    const triggersForBulk = Array.from(
      host.querySelectorAll('button[aria-label="Действия с лотом"]'),
    ) as HTMLButtonElement[]
    triggersForBulk[0]!.click()
    await flushUi()

    const multiSelectItem = Array.from(host.querySelectorAll('[role="menuitem"]')).find((el) =>
      el.textContent?.includes('Выбрать несколько'),
    ) as HTMLButtonElement
    multiSelectItem.click()
    await flushUi()

    const bulkBar = host.querySelector('[aria-label="Массовые действия с лотами"]')
    expect(bulkBar?.textContent).toContain('Выбрано: 1')

    const selectableCards = Array.from(
      host.querySelectorAll('main article [role="button"][aria-pressed]'),
    ) as HTMLElement[]
    expect(selectableCards.length).toBeGreaterThanOrEqual(2)
    expect(selectableCards[0]?.getAttribute('aria-pressed')).toBe('true')
    expect(selectableCards[1]?.getAttribute('aria-pressed')).toBe('false')
    selectableCards[1]!.click()
    await flushUi()
    expect(selectableCards[1]?.getAttribute('aria-pressed')).toBe('true')
    expect(bulkBar?.textContent).toContain('Выбрано: 2')

    const bulkDeleteBtn = Array.from(bulkBar?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Удалить (2)'),
    ) as HTMLButtonElement
    bulkDeleteBtn.click()
    await flushUi()

    expect(bulkDeleteSpy).toHaveBeenCalledWith([firstLot.lot_id, secondLot.lot_id])
  })
})
