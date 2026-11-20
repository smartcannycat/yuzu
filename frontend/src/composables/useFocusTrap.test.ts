import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { createApp } from 'vue'

import { useFocusTrap } from '@/composables/useFocusTrap'

describe('useFocusTrap', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
  })

  it('focuses immediately when active starts true and filters hidden/zero-rect focusables (preserving sr-only)', async () => {
    const active = ref(true)
    const containerRef = ref<HTMLElement | null>(null)

    const Comp = defineComponent({
      setup() {
        useFocusTrap(containerRef, active)
        return () =>
          h('div', { ref: containerRef, tabindex: '-1' }, [
            h('button', { type: 'button', style: 'display: none', id: 'disp-none' }, 'Hidden1'),
            h(
              'button',
              { type: 'button', style: 'visibility: hidden', id: 'vis-hidden' },
              'Hidden2',
            ),
            h(
              'button',
              { type: 'button', style: 'width: 0px; height: 0px', id: 'zero-box' },
              'Zero',
            ),
            h('button', { type: 'button', class: 'sr-only', id: 'sr-only-btn' }, 'SR Only'),
            h('button', { type: 'button', id: 'visible-btn' }, 'Visible'),
          ])
      },
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Comp)
    app.mount(host)

    await nextTick()
    await nextTick()

    expect(document.activeElement?.id).toBe('sr-only-btn')

    // Mock bounding rects to simulate real layout engine where zero-rect element is hidden
    const containerEl = containerRef.value!
    const srBtn = host.querySelector('#sr-only-btn') as HTMLElement
    const zeroBtn = host.querySelector('#zero-box') as HTMLElement
    const visibleBtn = host.querySelector('#visible-btn') as HTMLElement

    vi.spyOn(containerEl, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 300, 200))
    vi.spyOn(srBtn, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 0, 0))
    vi.spyOn(zeroBtn, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 0, 0))
    vi.spyOn(visibleBtn, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 100, 36))

    // Tab cycles strictly between sr-only-btn and visible-btn, skipping hidden/zero-box
    visibleBtn.focus()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    expect(document.activeElement?.id).toBe('sr-only-btn')

    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }),
    )
    expect(document.activeElement?.id).toBe('visible-btn')
  })

  it('aborts focusing if active flips back to false before nextTick completes', async () => {
    const triggerBtn = document.createElement('button')
    triggerBtn.textContent = 'Trigger'
    document.body.appendChild(triggerBtn)
    triggerBtn.focus()

    const active = ref(false)
    const containerRef = ref<HTMLElement | null>(null)

    const Comp = defineComponent({
      setup() {
        useFocusTrap(containerRef, active)
        return () =>
          h('div', { ref: containerRef, tabindex: '-1' }, [
            h('button', { type: 'button', id: 'inside-btn' }, 'Inside'),
          ])
      },
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Comp)
    app.mount(host)
    await nextTick()

    active.value = true
    await nextTick()
    active.value = false
    await nextTick()
    await nextTick()

    expect(document.activeElement).toBe(triggerBtn)
    triggerBtn.remove()
  })
})
