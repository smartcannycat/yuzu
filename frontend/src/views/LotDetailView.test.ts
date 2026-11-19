import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { apiClient } from '@/api'
import { clearAuthorizedImageCache } from '@/composables/useAuthorizedImage'
import { useLotDetailStore } from '@/stores/lotDetail'
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

  beforeAll(async () => {
    await import('@/api/mockApiClient')
  })

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

    return { host, router, lotsStore: useLotDetailStore() }
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

    expect(host.textContent).toContain('Себестоимость привоза во Владивосток под ключ')
    expect(host.textContent).toContain('VL.ru Деньги')

    // Inline JPY bid input works when clicked and submitted via Enter
    const editJpyBtn = host.querySelector(
      'button[aria-label="Изменить ставку в иенах"]',
    ) as HTMLButtonElement | null
    expect(editJpyBtn).not.toBeNull()
    editJpyBtn?.click()
    await flushUi()

    const jpyInput = host.querySelector(
      'input[aria-label="Введите ставку в иенах"]',
    ) as HTMLInputElement | null
    expect(jpyInput).not.toBeNull()
    if (jpyInput) {
      jpyInput.value = '1500000'
      jpyInput.dispatchEvent(new Event('input'))
      jpyInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
      await vi.advanceTimersByTimeAsync(250)
      await flushUi()
    }
    expect(lotsStore.currentLotDetail!.economics.wise_cost_ladder.car_bid_jpy).toBe(1_500_000)

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
    await vi.advanceTimersByTimeAsync(250)
    await flushUi()

    expect(lotsStore.isSimulationModified).toBe(false)
    expect(lotsStore.currentLotDetail!.economics.wise_cost_ladder.turnkey_cost_rub).toBe(
      baseTurnkey,
    )
  })

  it('neutralizes unsafe drom_search_url and sheet_scan_url payloads', async () => {
    const { host, lotsStore } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746501')

    lotsStore.currentLotDetail = {
      ...lotsStore.currentLotDetail!,
      media: {
        ...lotsStore.currentLotDetail!.media,
        drom_search_url: 'javascript:alert(1)',
        sheet_scan_url: 'data:text/html,<script>alert(1)</script>',
      },
    }
    await flushUi()

    const unsafeAnchor = host.querySelector('a[href^="javascript:"]')
    expect(unsafeAnchor).toBeNull()

    const scanRow = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Оригинальный аукционный лист'),
    )
    scanRow?.click()
    await flushUi()

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.querySelector('img')).toBeNull()
    expect(dialog?.textContent).toContain('Скан аукционного листа недоступен')
  })

  it('toggles archive status from header and deletes lot after confirmation redirecting to home', async () => {
    const { host, lotsStore, router } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746501')
    const replaceSpy = vi.spyOn(router, 'replace')
    const archiveSpy = vi
      .spyOn(lotsStore, 'setLotArchived')
      .mockImplementation(async (id, arch) => {
        lotsStore.currentLotDetail = {
          ...lotsStore.currentLotDetail!,
          lot_id: id,
          is_archived: arch,
          archived_at: arch ? '2026-11-13T10:00:00Z' : null,
          archived_reason: arch ? 'manual' : null,
        }
        return {
          lot_id: id,
          make: 'Toyota',
          model: 'Corolla Touring',
          year: 2021,
          engine_cc: 1797,
          frame_id: 'ZWE211-1234567',
          auction_house: 'USS',
          lot_number: '1001',
          overall_grade: '4.5',
          mileage_km: 32000,
          turnkey_cost_rub: 1850000,
          market_price_rf_rub: 2150000,
          verdict: 'green',
          verdict_headline: 'Хороший лот',
          net_benefit_rub: 300000,
          meti_sanction_risk: false,
          has_anomaly: false,
          anomaly_text: null,
          thumbnail_url: null,
          auction_date: null,
          is_archived: arch,
          archived_at: arch ? '2026-11-13T10:00:00Z' : null,
          archived_reason: arch ? 'manual' : null,
          expires_at: null,
          created_at: '2026-11-10T10:00:00Z',
        }
      })
    const deleteSpy = vi.spyOn(lotsStore, 'deleteLot').mockResolvedValue()

    const archiveButton = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('В архив'),
    )
    expect(archiveButton).toBeTruthy()
    archiveButton!.click()
    await flushUi()

    expect(archiveSpy).toHaveBeenCalledWith('892b4e10-3a2c-411f-a801-019283746501', true)
    expect(host.textContent).toContain('В архиве')
    expect(host.textContent).toContain('Из архива')

    const deleteButton = Array.from(host.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Удалить',
    )
    expect(deleteButton).toBeTruthy()
    deleteButton!.click()
    await flushUi()

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Удалить лот?')

    const confirmButton = Array.from(dialog?.querySelectorAll('button') ?? []).find((b) =>
      b.textContent?.includes('Удалить лот'),
    )
    expect(confirmButton).toBeTruthy()
    confirmButton!.click()
    await flushUi()

    expect(deleteSpy).toHaveBeenCalledWith('892b4e10-3a2c-411f-a801-019283746501')
    expect(replaceSpy).toHaveBeenCalledWith({ name: 'home' })
  })

  it('disables reset simulation button while recalculating and preserves LotTabEconomics drafts on archive update', async () => {
    const { host, lotsStore } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746501')

    const econTab = Array.from(host.querySelectorAll('[role="tab"]')).find((el) =>
      el.textContent?.includes('Экономика'),
    ) as HTMLButtonElement
    econTab.click()
    await flushUi()

    const hpInput = host.querySelector('#simulator-custom-power-hp') as HTMLInputElement
    hpInput.value = '155'
    hpInput.dispatchEvent(new Event('input'))
    await flushUi()

    // Unrelated detail replacement (like archiving) must NOT wipe unsaved power input
    lotsStore.currentLotDetail = {
      ...lotsStore.currentLotDetail!,
      is_archived: true,
      archived_reason: 'manual',
    }
    await flushUi()
    expect((host.querySelector('#simulator-custom-power-hp') as HTMLInputElement).value).toBe('155')

    // When simulation is modified & isRecalculating is true, header reset button is disabled
    lotsStore.currentLotDetail = {
      ...lotsStore.currentLotDetail!,
      economics: {
        ...lotsStore.currentLotDetail!.economics,
        is_simulation_modified: true,
      },
    }
    lotsStore.isRecalculating = true
    await flushUi()

    const resetTopBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Сбросить ставку'),
    ) as HTMLButtonElement | undefined
    expect(resetTopBtn?.disabled).toBe(true)
  })

  it('checks window.history.state?.back in goBack, marks RA and *** grades as danger in AuditSheet, and handles scan @error', async () => {
    clearAuthorizedImageCache()
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:scan/lot-scan-1')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)

    const { host, lotsStore, router } = await mountLotDetail('892b4e10-3a2c-411f-a801-019283746504')
    const pushSpy = vi.spyOn(router, 'push')
    const backSpy = vi.spyOn(router, 'back').mockImplementation(() => undefined)

    // Even when window.history.length > 1, missing history.state.back navigates to home
    const origHistoryState = window.history.state
    window.history.replaceState({ ...origHistoryState, back: null }, '')
    const backBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Назад'),
    ) as HTMLButtonElement
    backBtn.click()
    expect(pushSpy).toHaveBeenCalledWith({ name: 'home' })
    expect(backSpy).not.toHaveBeenCalled()

    // When history.state.back is present, router.back() is called
    window.history.replaceState({ ...origHistoryState, back: '/' }, '')
    backBtn.click()
    expect(backSpy).toHaveBeenCalledTimes(1)

    // Audit sheet recognizes RA and *** grades as danger
    lotsStore.currentLotDetail = {
      ...lotsStore.currentLotDetail!,
      audit: {
        ...lotsStore.currentLotDetail!.audit,
        history: [
          {
            auction_date: '01.10.2026',
            auction_house: 'USS Tokyo',
            auction_strictness: 0.9,
            lot_number: '2201',
            overall_grade: 'RA',
            mileage_km: 50000,
            defects_summary: 'XX',
            closing_price_jpy: 900000,
            sheet_archive_url: null,
          },
          {
            auction_date: '02.10.2026',
            auction_house: 'TAA',
            auction_strictness: 0.85,
            lot_number: '2202',
            overall_grade: '***',
            mileage_km: 50000,
            defects_summary: 'Аварийный',
            closing_price_jpy: 700000,
            sheet_archive_url: null,
          },
        ],
      },
    }
    await flushUi()

    const alertBtn = host.querySelector('[role="alert"] button') as HTMLButtonElement
    alertBtn.click()
    await flushUi()

    const auditDialog = document.body.querySelector('[role="dialog"]')!
    const raBadge = Array.from(auditDialog.querySelectorAll('span')).find((el) =>
      el.textContent?.includes('Оценка RA'),
    )
    const starBadge = Array.from(auditDialog.querySelectorAll('span')).find((el) =>
      el.textContent?.includes('Оценка ***'),
    )
    expect(raBadge?.className).toContain('text-danger')
    expect(starBadge?.className).toContain('text-danger')

    // Close audit sheet via Escape, open Scan sheet with protected media URL + test @error fallback
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushUi()

    const fetchBlobSpy = vi
      .spyOn(apiClient.media, 'fetchBlob')
      .mockResolvedValue(new Blob(['scan'], { type: 'image/jpeg' }))
    lotsStore.currentLotDetail = {
      ...lotsStore.currentLotDetail!,
      media: {
        ...lotsStore.currentLotDetail!.media,
        sheet_scan_url: '/api/v1/lots/lot-scan/media/scan',
      },
    }
    await flushUi()

    const scanRow = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Оригинальный аукционный лист'),
    )
    scanRow?.click()
    await flushUi()

    expect(fetchBlobSpy).toHaveBeenCalledWith(
      '/api/v1/lots/lot-scan/media/scan',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    const scanDialog = document.body.querySelector('[role="dialog"]')!
    const scanImg = scanDialog.querySelector('img') as HTMLImageElement | null
    expect(scanImg?.getAttribute('src')).toBe('blob:scan/lot-scan-1')

    scanImg?.dispatchEvent(new Event('error'))
    await flushUi()
    expect(scanDialog.querySelector('img')).toBeNull()
    expect(scanDialog.textContent).toContain('Скан аукционного листа недоступен')
    clearAuthorizedImageCache()
  })
})
