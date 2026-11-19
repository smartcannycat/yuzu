import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'

import LotsToolbar from '@/components/lots/LotsToolbar.vue'
import type { AvailableFilters } from '@/types/api'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'

const FILTERS: AvailableFilters = {
  makes: [{ value: 'Toyota', count: 3 }],
  models: [{ value: 'Corolla', count: 2 }],
  counts_by_verdict: { green: 2, yellow: 1, red: 0 },
  archived_lots_count: 0,
  total_lots_count: 3,
}

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
}

describe('LotsToolbar', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('displays TRAFFIC_LIGHT_META verdict pills, debounces search, and emits filter toggles', async () => {
    const onSearch = vi.fn()
    const onToggleVerdict = vi.fn()
    const onToggleModel = vi.fn()
    const onToggleAnomaly = vi.fn()
    const onResetFilters = vi.fn()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotsToolbar, {
      query: '',
      selectedModel: null,
      selectedVerdict: null,
      onlyAnomalies: false,
      activeFiltersCount: 1,
      hasAnyActiveFilter: true,
      hasLoadedOnce: true,
      availableFilters: FILTERS,
      onSearch,
      onToggleVerdict,
      onToggleModel,
      onToggleAnomaly,
      onResetFilters,
    })
    app.mount(host)
    await flushUi()

    expect(host.textContent).toContain(TRAFFIC_LIGHT_META.green.label)
    expect(host.textContent).toContain(TRAFFIC_LIGHT_META.yellow.label)
    expect(host.textContent).toContain(TRAFFIC_LIGHT_META.red.label)

    const greenPill = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes(TRAFFIC_LIGHT_META.green.label),
    )
    greenPill?.click()
    expect(onToggleVerdict).toHaveBeenCalledWith('green')

    const modelBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Corolla (2)'),
    )
    modelBtn?.click()
    expect(onToggleModel).toHaveBeenCalledWith('Corolla')

    const anomalyBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Аномалии'),
    )
    anomalyBtn?.click()
    expect(onToggleAnomaly).toHaveBeenCalledTimes(1)

    const searchInput = host.querySelector('input[type="search"]') as HTMLInputElement
    searchInput.value = 'Corolla'
    searchInput.dispatchEvent(new Event('input'))
    await flushUi()
    expect(onSearch).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(260)
    expect(onSearch).toHaveBeenCalledWith('Corolla')

    const resetBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Сбросить'),
    )
    resetBtn?.click()
    expect(onResetFilters).toHaveBeenCalledTimes(1)
  })
})
