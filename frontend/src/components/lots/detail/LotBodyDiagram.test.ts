import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'

import LotBodyDiagram from '@/components/lots/detail/LotBodyDiagram.vue'
import type { NormalizedDefect } from '@/types/api'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
}

function makeDefect(overrides: Partial<NormalizedDefect>): NormalizedDefect {
  return {
    panel_id: 'front_left_door',
    panel_ru: 'Передняя левая дверь',
    defect_types: ['A'],
    severity: 1,
    raw_code: 'A1',
    description_ru: 'Царапина',
    ...overrides,
  }
}

describe('LotBodyDiagram', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
  })

  it('picks the highest-severity defect per panel (XX > X > severity 3 > 2 > 1)', async () => {
    const defects: NormalizedDefect[] = [
      makeDefect({ panel_id: 'hood', panel_ru: 'Капот', raw_code: 'A1', severity: 1 }),
      makeDefect({ panel_id: 'hood', panel_ru: 'Капот', raw_code: 'W2', severity: 2 }),
      makeDefect({ panel_id: 'hood', panel_ru: 'Капот', raw_code: 'A3', severity: 3 }),
      makeDefect({
        panel_id: 'hood',
        panel_ru: 'Капот',
        raw_code: 'X',
        defect_types: ['X'],
        severity: 2,
      }),
      makeDefect({
        panel_id: 'hood',
        panel_ru: 'Капот',
        raw_code: 'XX',
        defect_types: ['XX'],
        severity: 1,
      }),
      makeDefect({
        panel_id: 'front_left_door',
        raw_code: 'A2',
        severity: 2,
      }),
      makeDefect({
        panel_id: 'front_left_door',
        raw_code: 'X1',
        defect_types: ['X'],
        severity: 1,
      }),
      makeDefect({
        panel_id: 'rear_bumper',
        panel_ru: 'Задний бампер',
        raw_code: 'U1',
        severity: 1,
      }),
      makeDefect({
        panel_id: 'rear_bumper',
        panel_ru: 'Задний бампер',
        raw_code: 'U3',
        severity: 3,
      }),
    ]

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotBodyDiagram, {
      defects,
      selectedPanel: null,
    })
    app.mount(host)
    await flushUi()

    const pinLabels = Array.from(host.querySelectorAll('svg g[role="button"] text')).map((el) =>
      el.textContent?.trim(),
    )
    expect(pinLabels).toEqual(['XX', 'X1', 'U3'])
  })

  it('renders unpinned "other" defects in the unpinned list without crashing SVG pin lookup', async () => {
    const onSelectPanel = vi.fn()
    const defects: NormalizedDefect[] = [
      makeDefect({ panel_id: 'hood', panel_ru: 'Капот', raw_code: 'A1', severity: 1 }),
      makeDefect({
        panel_id: 'other',
        panel_ru: 'Подкапотное пространство',
        raw_code: 'S2',
        defect_types: ['S'],
        severity: 2,
      }),
    ]

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotBodyDiagram, {
      defects,
      selectedPanel: null,
      'onUpdate:selectedPanel': onSelectPanel,
    })
    app.mount(host)
    await flushUi()

    const pins = host.querySelectorAll('svg g[role="button"]')
    expect(pins.length).toBe(1)
    expect(host.textContent).toContain('Вне схемы кузова')
    expect(host.textContent).toContain('Подкапотное пространство')

    const unpinnedBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Подкапотное пространство'),
    )
    expect(unpinnedBtn).toBeTruthy()
    unpinnedBtn!.click()
    expect(onSelectPanel).toHaveBeenCalledWith('other')
  })
})
