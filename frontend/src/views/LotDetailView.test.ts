import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useLotsStore } from '@/stores/lots'
import LotDetailView from '@/views/LotDetailView.vue'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('LotDetailView (Screens 4, 5, 6)', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    vi.useFakeTimers()
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

  async function mountLotDetail(lotId: string) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        { path: '/lots/:lotId', name: 'lot-detail', component: LotDetailView },
      ],
    })
    await router.push(`/lots/${lotId}`)
    await router.isReady()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotDetailView)
    app.use(pinia)
    app.use(router)
    app.mount(host)

    // Advance mock API delay (default 280ms -> clamped 160ms)
    await vi.advanceTimersByTimeAsync(400)
    await flushUi()

    return { host, router, lotsStore: useLotsStore() }
  }

  it('renders Screen 4 General tab cleanly without Sticky Danger Alert on clean Corolla lot', async () => {
    const { host } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746501')

    expect(host.textContent).toContain('Toyota Corolla Touring')
    expect(host.textContent).toContain('Паспорт и ТТХ')
    expect(host.textContent).toContain('Себестоимость под ключ')
    expect(host.querySelector('[role="alert"]')).toBeNull()

    const originalPrint = window.print
    const printMock = vi.fn()
    Object.defineProperty(window, 'print', {
      value: printMock,
      configurable: true,
      writable: true,
    })

    try {
      const pdfButton = Array.from(host.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('PDF'),
      )
      pdfButton?.click()
      expect(printMock).toHaveBeenCalledTimes(1)
    } finally {
      Object.defineProperty(window, 'print', {
        value: originalPrint,
        configurable: true,
        writable: true,
      })
    }
  })

  it('renders Sticky Danger Alert on critical Harrier lot and opens Audit sheet on click', async () => {
    const { host } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746504')

    const alertEl = host.querySelector('[role="alert"]')
    expect(alertEl).not.toBeNull()
    expect(alertEl?.textContent).toContain('Критическое предупреждение кросс-аудита')

    const alertBtn = alertEl?.querySelector('button')
    alertBtn?.click()
    await flushUi()

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('История торгов и аудит')
    expect(dialog?.textContent).toContain('Подозрение на скрученный пробег')
  })

  it('switches to Tech tab (Screen 5) with interactive SVG pins and opens Repair sheet', async () => {
    const { host } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746501')

    const techTab = Array.from(host.querySelectorAll('[role="tab"]')).find((el) =>
      el.textContent?.includes('Техника'),
    ) as HTMLButtonElement
    techTab.click()
    await flushUi()

    expect(host.textContent).toContain('Схема дефектов кузова')
    const pinButton = host.querySelector('svg g[role="button"]') as SVGGElement | null
    expect(pinButton).not.toBeNull()

    const repairRow = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Смета ремонта Farpost'),
    )
    repairRow?.click()
    await flushUi()

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Передняя левая дверь')
  })

  it('switches to Economics tab (Screen 6), recalculates across tabs, and resets cleanly', async () => {
    const { host, lotsStore } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746501')
    const baseTurnkey = lotsStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub

    const econTab = Array.from(host.querySelectorAll('[role="tab"]')).find((el) =>
      el.textContent?.includes('Экономика'),
    ) as HTMLButtonElement
    econTab.click()
    await flushUi()

    expect(host.textContent).toContain('Лестница себестоимости во Владивостоке')

    const utilSwitch = host.querySelector('button[role="switch"]') as HTMLButtonElement
    utilSwitch.click()
    await vi.advanceTimersByTimeAsync(250)
    await flushUi()

    expect(lotsStore.isSimulationModified).toBe(true)
    expect(lotsStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub).toBeGreaterThan(
      baseTurnkey,
    )

    const resetButton = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Сбросить ставку'),
    )
    resetButton?.click()
    await flushUi()

    expect(lotsStore.isSimulationModified).toBe(false)
    expect(lotsStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub).toBe(
      baseTurnkey,
    )
  })
})
