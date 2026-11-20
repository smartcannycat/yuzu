import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, nextTick, ref } from 'vue'

import BrandLogo from './BrandLogo.vue'

describe('BrandLogo', () => {
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
      components: { BrandLogo },
      template: '<div><BrandLogo layout="header" /><BrandLogo layout="auth" /></div>',
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Wrapper)
    app.mount(host)

    expect(randomSpy).not.toHaveBeenCalled()

    const clipIds = Array.from(host.querySelectorAll('clipPath')).map((el) => el.getAttribute('id'))
    expect(clipIds).toHaveLength(8)
    expect(new Set(clipIds).size).toBe(8)
  })

  it('cancels rAF immediately when animated changes to false and on unmount', async () => {
    const animated = ref(true)
    const Wrapper = defineComponent({
      components: { BrandLogo },
      setup() {
        return { animated }
      },
      template: '<BrandLogo layout="header" :animated="animated" />',
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

  it('emits boop count on click and keyboard activation only when animated=true', async () => {
    const animated = ref(true)
    const boopCounts: number[] = []

    const Wrapper = defineComponent({
      components: { BrandLogo },
      setup() {
        return {
          animated,
          onBoop: (count: number) => boopCounts.push(count),
        }
      },
      template: '<BrandLogo layout="report" :animated="animated" @boop="onBoop" />',
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Wrapper)
    app.mount(host)

    const rootButton = host.querySelector('[role="button"]') as HTMLElement
    expect(rootButton).not.toBeNull()
    expect(host.textContent).toContain('Report')

    rootButton.click()
    rootButton.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    rootButton.dispatchEvent(new KeyboardEvent('keydown', { key: ' ' }))
    await nextTick()
    expect(boopCounts).toEqual([1, 2, 3])

    animated.value = false
    await nextTick()
    expect(host.querySelector('[role="button"]')).toBeNull()

    const staticRoot = host.firstElementChild as HTMLElement
    staticRoot.click()
    await nextTick()
    expect(boopCounts).toEqual([1, 2, 3])
  })

  it('never starts rAF on mount when animated=false and renders mark/wordmark/swiss variants', () => {
    const Wrapper = defineComponent({
      components: { BrandLogo },
      template: `
        <div>
          <BrandLogo layout="mark" :size="60" :animated="false" />
          <BrandLogo
            layout="header"
            variant="wordmark"
            wordmark-style="swiss"
            subtitle="Тест"
            :animated="false"
          />
        </div>
      `,
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Wrapper)
    app.mount(host)

    expect(pendingCallbacks.size).toBe(0)
    const svgs = host.querySelectorAll('svg')
    expect(svgs[0]?.getAttribute('width')).toBe('60')
    expect(host.textContent).toContain('YUZU')
    expect(host.textContent).toContain('Тест')
  })
})
