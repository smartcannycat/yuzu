import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import { useBatchesStore } from '@/stores/batches'
import type { BatchProgressResponse } from '@/types/api'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'
import BatchProgressView from '@/views/BatchProgressView.vue'

let mockSubmitFiles: File[] = []

vi.mock('@/components/lots/BatchUploadSheet.vue', () => ({
  default: defineComponent({
    name: 'BatchUploadSheet',
    props: {
      open: { type: Boolean, default: false },
      mode: { type: String, default: 'append' },
      maxFiles: { type: Number, default: 10 },
      isSubmitting: { type: Boolean, default: false },
      serverError: { type: String, default: null },
    },
    emits: ['update:open', 'submit'],
    setup(props, { emit }) {
      return () =>
        h('div', { 'data-testid': 'mock-upload-sheet', 'data-open': String(props.open) }, [
          props.serverError
            ? h('div', { 'data-testid': 'mock-sheet-error' }, props.serverError)
            : null,
          h(
            'button',
            {
              type: 'button',
              'data-testid': 'mock-sheet-submit',
              onClick: () => emit('submit', mockSubmitFiles),
            },
            'Submit',
          ),
        ])
    },
  }),
}))

function makeBatchResponse(overrides: Partial<BatchProgressResponse> = {}): BatchProgressResponse {
  const readySummary = SEEDED_MOCK_LOTS[0]!
  return {
    batch_id: 'batch-1',
    status: 'completed',
    total_count: 3,
    processed_count: 3,
    ready_count: 2,
    failed_count: 1,
    mascot: {
      mood: 'happy',
      phrase_ru: 'Готово',
      badge_text: '2 из 3 готовы',
    },
    items: [
      {
        file_index: 0,
        original_filename: 'corolla.jpg',
        status: 'ready',
        current_step: 'completed',
        lot_id: readySummary.lot_id,
        preview_title: null,
        error_message: null,
        summary: readySummary,
      },
      {
        file_index: 1,
        original_filename: 'deleted.jpg',
        status: 'ready',
        current_step: 'completed',
        lot_id: 'lot-deleted',
        preview_title: 'Toyota Aqua',
        error_message: null,
        summary: null,
      },
      {
        file_index: 2,
        original_filename: 'blurry.jpg',
        status: 'failed',
        current_step: 'failed',
        lot_id: null,
        preview_title: null,
        error_message: 'Нечитаемый бланк',
        summary: null,
      },
    ],
    ...overrides,
  }
}

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('BatchProgressView', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    vi.useFakeTimers()
    mockSubmitFiles = [new File(['img'], 'extra.jpg', { type: 'image/jpeg' })]
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

  async function mountView(batchId = 'batch-1') {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        { path: '/lots/:lotId', name: 'lot-detail', component: { template: '<div />' } },
        { path: '/batches/:batchId', name: 'batch-progress', component: BatchProgressView },
      ],
    })
    await router.push(`/batches/${batchId}`)
    await router.isReady()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(BatchProgressView)
    app.use(pinia)
    app.use(router)
    app.mount(host)

    return { host, router, batchesStore: useBatchesStore() }
  }

  it('renders ready, deleted, and failed items using canonical TRAFFIC_LIGHT_META labels', async () => {
    const batchesStore = useBatchesStore()
    const batch = makeBatchResponse()
    vi.spyOn(batchesStore, 'fetchBatch').mockImplementation(async () => {
      batchesStore.activeBatch = batch
      return batch
    })

    const { host, router } = await mountView('batch-1')
    await flushUi()

    expect(host.textContent).toContain(TRAFFIC_LIGHT_META[SEEDED_MOCK_LOTS[0]!.verdict].label)
    expect(host.textContent).toContain('Лот удалён из списка')
    expect(host.textContent).toContain('Нечитаемый бланк')

    const pushSpy = vi.spyOn(router, 'push')
    const readyBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Toyota Corolla Touring'),
    )
    readyBtn?.click()
    expect(pushSpy).toHaveBeenCalledWith({
      name: 'lot-detail',
      params: { lotId: SEEDED_MOCK_LOTS[0]!.lot_id },
    })
  })

  it('stops polling immediately on 404 and clears pending timers on unmount', async () => {
    const batchesStore = useBatchesStore()
    const fetchSpy = vi.spyOn(batchesStore, 'fetchBatch').mockImplementationOnce(async () => {
      batchesStore.batchError = 'Очередь не найдена'
      batchesStore.batchErrorStatus = 404
      return null
    })

    await mountView('missing-batch')
    await flushUi()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(10_000)
    await flushUi()
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    // Verify unmount stops active polling timer during processing
    app?.unmount()
    host?.remove()

    const processingBatch = makeBatchResponse({ status: 'processing', processed_count: 1 })
    fetchSpy.mockImplementation(async () => {
      batchesStore.activeBatch = processingBatch
      return processingBatch
    })

    await mountView('batch-active')
    await flushUi()
    expect(fetchSpy).toHaveBeenCalledTimes(2)

    app?.unmount()
    app = null
    await vi.advanceTimersByTimeAsync(10_000)
    await flushUi()
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('catches appendItems and createBatch errors gracefully without unhandled rejection', async () => {
    const batchesStore = useBatchesStore()
    const activeBatch = makeBatchResponse({
      status: 'processing',
      processed_count: 1,
      failed_count: 0,
    })
    vi.spyOn(batchesStore, 'fetchBatch').mockImplementation(async () => {
      batchesStore.activeBatch = activeBatch
      return activeBatch
    })
    vi.spyOn(batchesStore, 'appendItems').mockRejectedValue(new Error('Сервер перегружен'))

    const { host } = await mountView('batch-1')
    await flushUi()

    const appendBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Догрузить ещё листы'),
    )
    appendBtn?.click()
    await flushUi()

    const submitBtn = host.querySelector('[data-testid="mock-sheet-submit"]') as HTMLButtonElement
    submitBtn.click()
    await flushUi()

    expect(host.querySelector('[data-testid="mock-sheet-error"]')?.textContent).toContain(
      'Сервер перегружен',
    )
    expect(host.querySelector('[data-testid="mock-upload-sheet"]')?.getAttribute('data-open')).toBe(
      'true',
    )
  })
})
