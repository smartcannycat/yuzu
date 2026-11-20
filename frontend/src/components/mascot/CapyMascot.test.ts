import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, nextTick, ref } from 'vue'

import CapyMascot from './CapyMascot.vue'

describe('CapyMascot', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null
  let nextFrameId = 1
  let pendingCallbacks = new Map<number, FrameRequestCallback>()
  let cancelledIds: number[] = []

  beforeEach(() => {
    nextFrameId = 1
    pendingCallbacks = new Map()
    cancelledIds = []

    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      const id = nextFrameId++
      pendingCallbacks.set(id, cb)
      return id
    })
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      cancelledIds.push(id)
      pendingCallbacks.delete(id)
    })
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uses Vue useId() for SVG clipPaths without calling Math.random()', () => {
    const randomSpy = vi.spyOn(Math, 'random')
    const Wrapper = defineComponent({
      components: { CapyMascot },
      template: '<div><CapyMascot state="thinking" /><CapyMascot state="sleeping" /></div>',
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Wrapper)
    app.mount(host)

    expect(randomSpy).not.toHaveBeenCalled()

    const clipElements = Array.from(host.querySelectorAll('clipPath'))
    expect(clipElements.every((el) => el.namespaceURI === 'http://www.w3.org/2000/svg')).toBe(true)
    const clipIds = clipElements.map((el) => el.getAttribute('id'))
    expect(clipIds.length).toBeGreaterThanOrEqual(6)
    expect(new Set(clipIds).size).toBe(clipIds.length)
    expect(clipIds.every((id) => Boolean(id) && !String(id).includes('undefined'))).toBe(true)

    const clipRefs = Array.from(host.querySelectorAll('[clip-path]')).map((el) =>
      el.getAttribute('clip-path'),
    )
    for (const clipRef of clipRefs) {
      const targetId = clipRef?.replace(/^url\(#(.+)\)$/, '$1')
      expect(clipIds).toContain(targetId)
    }
  })

  it('stops rAF when animated becomes false and on unmount', async () => {
    const animated = ref(true)
    const Wrapper = defineComponent({
      components: { CapyMascot },
      setup() {
        return { animated }
      },
      template: '<CapyMascot state="green" :animated="animated" />',
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Wrapper)
    app.mount(host)

    expect(pendingCallbacks.size).toBe(1)

    animated.value = false
    await nextTick()
    expect(cancelledIds).toEqual([1])
    expect(pendingCallbacks.size).toBe(0)

    animated.value = true
    await nextTick()
    expect(pendingCallbacks.size).toBe(1)

    app.unmount()
    app = null
    expect(cancelledIds).toEqual([1, 2])
    expect(pendingCallbacks.size).toBe(0)
  })

  it('resolves contract props, custom badge text, and hides badge in compact mode', () => {
    const Wrapper = defineComponent({
      components: { CapyMascot },
      template: `
        <div>
          <CapyMascot verdict="green" badge-text="Одобрено" />
          <CapyMascot verdict="red" size="compact" />
        </div>
      `,
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Wrapper)
    app.mount(host)

    const containers = host.querySelectorAll('.mascot-container')
    expect(containers).toHaveLength(2)
    expect(containers[0]?.textContent).toContain('Одобрено')
    expect(containers[1]?.textContent?.trim()).toBe('')
    expect(containers[1]?.querySelector('svg')?.getAttribute('aria-label')).toContain('Стоп-фактор')
  })
})
