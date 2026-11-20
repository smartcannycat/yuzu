import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'

import { apiClient } from '@/api'
import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import LotCard from '@/components/lots/LotCard.vue'
import { clearAuthorizedImageCache } from '@/composables/useAuthorizedImage'
import { TRAFFIC_LIGHT_META } from '@/utils/lotPresentation'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('LotCard', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  beforeEach(() => {
    clearAuthorizedImageCache()
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:lot-card/thumb-1')
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

  it('keeps valid ARIA structure with sibling action menu (no nested buttons or menu inside role="button")', async () => {
    const lot = { ...SEEDED_MOCK_LOTS[0]! }
    const onSelect = vi.fn()
    const onToggleMenu = vi.fn()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotCard, {
      lot,
      menuOpen: true,
      selectionMode: false,
      onSelect,
      onToggleMenu,
    })
    app.mount(host)
    await flushUi()

    expect(host.textContent).toContain(TRAFFIC_LIGHT_META[lot.verdict].label)
    expect(host.querySelector('[role="button"] button')).toBeNull()
    expect(host.querySelector('[role="button"] [role="menu"]')).toBeNull()
    expect(host.querySelector('button button')).toBeNull()
    expect(host.querySelector('button [role="menu"]')).toBeNull()

    const menuTrigger = host.querySelector(
      'button[aria-label="Действия с лотом"]',
    ) as HTMLButtonElement
    expect(menuTrigger).not.toBeNull()
    expect(host.querySelector('[role="menu"]')).not.toBeNull()

    menuTrigger.click()
    expect(onToggleMenu).toHaveBeenCalledWith(lot.lot_id)
    expect(onSelect).not.toHaveBeenCalled()

    const titleEl = host.querySelector('h3') as HTMLElement
    titleEl.click()
    expect(onSelect).toHaveBeenCalledWith(lot)
  })

  it('loads protected thumbnail via useAuthorizedImage, passes data: URLs through, and falls back on @error', async () => {
    const fetchBlobSpy = vi
      .spyOn(apiClient.media, 'fetchBlob')
      .mockResolvedValue(new Blob(['img'], { type: 'image/jpeg' }))

    const protectedLot = {
      ...SEEDED_MOCK_LOTS[0]!,
      thumbnail_url: '/api/v1/lots/lot-1/media/thumbnail',
    }

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LotCard, { lot: protectedLot })
    app.mount(host)
    await flushUi()

    expect(fetchBlobSpy).toHaveBeenCalledWith(
      '/api/v1/lots/lot-1/media/thumbnail',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    const img = host.querySelector('img') as HTMLImageElement | null
    expect(img?.getAttribute('src')).toBe('blob:lot-card/thumb-1')

    // Triggering @error falls back to placeholder without broken img
    img?.dispatchEvent(new Event('error'))
    await flushUi()
    expect(host.querySelector('img')).toBeNull()
    expect(host.textContent).toContain('Скан листа')

    // Data URL passes through without calling fetchBlob
    app.unmount()
    fetchBlobSpy.mockClear()
    const dataLot = {
      ...SEEDED_MOCK_LOTS[0]!,
      thumbnail_url: 'data:image/svg+xml;charset=utf-8,%3Csvg%3E%3C/svg%3E',
    }
    app = createApp(LotCard, { lot: dataLot })
    app.mount(host)
    await flushUi()

    expect(fetchBlobSpy).not.toHaveBeenCalled()
    expect(host.querySelector('img')?.getAttribute('src')).toBe(dataLot.thumbnail_url)
  })
})
