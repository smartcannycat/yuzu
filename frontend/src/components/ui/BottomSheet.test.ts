import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, ref } from 'vue'

import { buildMockLotDetail } from '@/api/mock/lotDetails'
import { SEEDED_MOCK_LOTS } from '@/api/mock/lotsSeed'
import LotDetailSheets, {
  type LotDetailSheetKind,
} from '@/components/lots/detail/LotDetailSheets.vue'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import { getElementScrollLockCount } from '@/composables/useScrollLock'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

function setMobileMatchMedia(): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
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

describe('BottomSheet & LotDetailSheets', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  beforeEach(() => {
    setMobileMatchMedia()
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
  })

  it('clears drag offset and dragging state on @touchcancel without closing the sheet', async () => {
    const open = ref(true)
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp({
      components: { BottomSheet },
      setup: () => ({ open }),
      template: '<BottomSheet v-model:open="open" title="Тест">Контент</BottomSheet>',
    })
    app.mount(host)
    await flushUi()

    const dialog = document.body.querySelector('[role="dialog"]') as HTMLElement
    const grabber = dialog.querySelector('div.touch-none') as HTMLElement
    expect(grabber).not.toBeNull()

    const startEvt = Object.assign(new Event('touchstart', { bubbles: true }), {
      touches: [{ clientY: 100 }],
    })
    const moveEvt = Object.assign(new Event('touchmove', { bubbles: true }), {
      touches: [{ clientY: 220 }],
    })
    grabber.dispatchEvent(startEvt)
    grabber.dispatchEvent(moveEvt)
    await flushUi()
    expect(dialog.style.transform).toContain('translateY(120px)')

    grabber.dispatchEvent(new Event('touchcancel', { bubbles: true }))
    await flushUi()
    expect(dialog.style.transform).toBe('')
    expect(open.value).toBe(true)
  })

  it('coordinates stacked BottomSheets on Escape & scroll lock and renders only active LotDetailSheet', async () => {
    const baseOpen = ref(true)
    const topOpen = ref(true)
    host = document.createElement('div')
    document.body.appendChild(host)

    app = createApp({
      components: { BottomSheet },
      setup: () => ({ baseOpen, topOpen }),
      template: `
        <div>
          <BottomSheet v-model:open="baseOpen" title="Нижняя шторка">Base</BottomSheet>
          <BottomSheet v-model:open="topOpen" title="Верхняя шторка">Top</BottomSheet>
        </div>
      `,
    })
    app.mount(host)
    await flushUi()

    expect(document.body.querySelectorAll('[role="dialog"]').length).toBe(2)
    expect(getElementScrollLockCount(document.body)).toBe(2)

    // First Escape closes only the top-most sheet
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushUi()
    expect(topOpen.value).toBe(false)
    expect(baseOpen.value).toBe(true)
    expect(getElementScrollLockCount(document.body)).toBe(1)

    // Second Escape closes the remaining base sheet and releases scroll lock
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushUi()
    expect(baseOpen.value).toBe(false)
    expect(getElementScrollLockCount(document.body)).toBe(0)

    // Verify LotDetailSheets mounts only the active open sheet
    app.unmount()
    const activeSheet = ref<LotDetailSheetKind>(null)
    const detail = buildMockLotDetail(SEEDED_MOCK_LOTS[0]!)
    app = createApp({
      components: { LotDetailSheets },
      setup: () => ({ activeSheet, detail }),
      template: '<LotDetailSheets v-model:active-sheet="activeSheet" :detail="detail" />',
    })
    app.mount(host)
    await flushUi()
    expect(document.body.querySelectorAll('[role="dialog"]').length).toBe(0)

    activeSheet.value = 'audit'
    await flushUi()
    expect(document.body.querySelectorAll('[role="dialog"]').length).toBe(1)
    expect(document.body.querySelector('[role="dialog"]')?.textContent).toContain(
      'История торгов и аудит',
    )

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushUi()
    expect(activeSheet.value).toBeNull()
    expect(document.body.querySelectorAll('[role="dialog"]').length).toBe(0)
    expect(getElementScrollLockCount(document.body)).toBe(0)
  })
})
