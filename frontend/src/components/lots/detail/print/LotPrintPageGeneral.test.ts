import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'

import { apiClient } from '@/api'
import { buildMockLotDetail } from '@/api/mock/lotDetails'
import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import LotPrintPageGeneral from '@/components/lots/detail/print/LotPrintPageGeneral.vue'
import { clearAuthorizedImageCache } from '@/composables/useAuthorizedImage'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('LotPrintPageGeneral', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  beforeEach(() => {
    clearAuthorizedImageCache()
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:print/thumb-1')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    clearAuthorizedImageCache()
    vi.restoreAllMocks()
  })

  it('omits spread row and hardcoded region when min === max or missing, and hides grand_total_repair_rub when repairs excluded', async () => {
    const detail = buildMockLotDetail(SEEDED_MOCK_LOTS[2]!)
    detail.market.price_min_rub = 1_500_000
    detail.market.price_max_rub = 1_500_000
    detail.market.search_region_ru = 'Владивосток'
    detail.economics.is_repairs_included = false
    detail.economics.farpost_repair.grand_total_repair_rub = 64_000
    detail.media.sheet_thumbnail_url = '/api/v1/lots/lot-print/media/thumbnail'

    const fetchBlobSpy = vi
      .spyOn(apiClient.media, 'fetchBlob')
      .mockResolvedValue(new Blob(['img'], { type: 'image/jpeg' }))

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotPrintPageGeneral, {
      detail,
      reportDateLabel: '19.11.2026',
    })
    app.mount(host)
    await flushUi()

    expect(host.textContent).not.toContain('Разброс цен в ДФО')
    expect(host.textContent).not.toContain('Владивосток')
    expect(host.textContent).not.toContain('64\u00A0000')
    expect(host.textContent).toContain('Исключён (0 ₽)')

    expect(fetchBlobSpy).toHaveBeenCalledWith(
      '/api/v1/lots/lot-print/media/thumbnail',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(host.querySelector('img')?.getAttribute('src')).toBe('blob:print/thumb-1')
  })

  it('shows regional spread row when min < max', async () => {
    const detail = buildMockLotDetail(SEEDED_MOCK_LOTS[0]!)
    detail.market.price_min_rub = 1_600_000
    detail.market.price_max_rub = 2_050_000
    detail.market.search_region_ru = 'Приморский край'

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotPrintPageGeneral, {
      detail,
      reportDateLabel: '19.11.2026',
    })
    app.mount(host)
    await flushUi()

    expect(host.textContent).toContain('Разброс в наличии (Приморский край)')
    expect(host.textContent).toContain('1\u00A0600\u00A0000 ₽ – 2\u00A0050\u00A0000 ₽')
  })
})
