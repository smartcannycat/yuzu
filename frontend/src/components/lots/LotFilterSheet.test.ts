import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, ref } from 'vue'

import LotFilterSheet from '@/components/lots/LotFilterSheet.vue'
import type { AvailableFilters } from '@/types/api'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'

const AVAILABLE_FILTERS: AvailableFilters = {
  makes: [
    { value: 'Toyota', count: 3 },
    { value: 'Honda', count: 2 },
  ],
  models: [
    { value: 'Corolla', count: 2 },
    { value: 'Vezel', count: 2 },
  ],
  counts_by_verdict: {
    green: 2,
    yellow: 2,
    red: 1,
  },
  archived_lots_count: 1,
  total_lots_count: 5,
}

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('LotFilterSheet', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
  })

  it('reuses TRAFFIC_LIGHT_META and prevents redundant previewFilters calls on open and reset', async () => {
    const open = ref(false)
    const makeProp = ref<string | null>('Toyota')
    const previewFilters = vi.fn(async () => AVAILABLE_FILTERS)
    const onApply = vi.fn()
    const onReset = vi.fn()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp({
      components: { LotFilterSheet },
      setup() {
        return {
          open,
          makeProp,
          availableFilters: AVAILABLE_FILTERS,
          previewFilters,
          onApply,
          onReset,
        }
      },
      template: `
        <LotFilterSheet
          v-model:open="open"
          :available-filters="availableFilters"
          lifecycle="active"
          :make="makeProp"
          :verdict="null"
          :only-anomalies="false"
          sort-by="created_at"
          sort-order="desc"
          :preview-filters="previewFilters"
          @apply="onApply"
          @reset="onReset"
        />
      `,
    })
    app.mount(host)
    await flushUi()

    // Change external make prop while closed, then open sheet -> must NOT trigger previewFilters
    makeProp.value = 'Honda'
    await flushUi()
    open.value = true
    await flushUi()

    expect(previewFilters).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(TRAFFIC_LIGHT_META.green.label)
    expect(document.body.textContent).toContain(TRAFFIC_LIGHT_META.yellow.label)
    expect(document.body.textContent).toContain(TRAFFIC_LIGHT_META.red.label)

    // User selects verdict -> triggers previewFilters once
    const greenBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes(TRAFFIC_LIGHT_META.green.label),
    )
    greenBtn?.click()
    await flushUi()
    expect(previewFilters).toHaveBeenCalledTimes(1)

    // Resetting must NOT fire another previewFilters request
    const resetBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Сбросить'),
    )
    resetBtn?.click()
    await flushUi()
    expect(onReset).toHaveBeenCalledTimes(1)
    expect(previewFilters).toHaveBeenCalledTimes(1)
  })
})
