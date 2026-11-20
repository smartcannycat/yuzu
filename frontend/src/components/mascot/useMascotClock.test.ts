import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, nextTick, ref } from 'vue'

import { useMascotClock } from './useMascotClock'

describe('useMascotClock', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null
  let nextFrameId = 1
  let pendingCallbacks = new Map<number, FrameRequestCallback>()
  let cancelledIds: number[] = []
  let ioCallbacks: Array<(entries: Array<{ isIntersecting: boolean }>) => void> = []
  let ioDisconnectSpy = vi.fn()
  let mqlMatches = false
  let mqlListeners: Array<() => void> = []

  beforeEach(() => {
    nextFrameId = 1
    pendingCallbacks = new Map()
    cancelledIds = []
    ioCallbacks = []
    ioDisconnectSpy = vi.fn()
    mqlMatches = false
    mqlListeners = []

    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      const id = nextFrameId++
      pendingCallbacks.set(id, cb)
      return id
    })
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      cancelledIds.push(id)
      pendingCallbacks.delete(id)
    })
    vi.stubGlobal(
      'IntersectionObserver',
      class MockIntersectionObserver {
        constructor(cb: (entries: Array<{ isIntersecting: boolean }>) => void) {
          ioCallbacks.push(cb)
        }
        observe() {}
        disconnect() {
          ioDisconnectSpy()
        }
      },
    )
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: () => ({
        get matches() {
          return mqlMatches
        },
        addEventListener: (_event: string, listener: () => void) => {
          mqlListeners.push(listener)
        },
        removeEventListener: (_event: string, listener: () => void) => {
          mqlListeners = mqlListeners.filter((item) => item !== listener)
        },
      }),
    })
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  function mountClock(initialAnimated = true) {
    const animated = ref(initialAnimated)
    let clockApi!: ReturnType<typeof useMascotClock>

    const Comp = defineComponent({
      setup() {
        clockApi = useMascotClock({ animated })
        return { root: clockApi.root }
      },
      template: '<div ref="root" />',
    })

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(Comp)
    app.mount(host)
    return { animated, clockApi }
  }

  it('starts rAF on mount when animated=true and cancels immediately when animated becomes false', async () => {
    const { animated } = mountClock(true)
    expect(pendingCallbacks.size).toBe(1)

    animated.value = false
    await nextTick()

    expect(cancelledIds).toEqual([1])
    expect(pendingCallbacks.size).toBe(0)

    animated.value = true
    await nextTick()
    expect(pendingCallbacks.size).toBe(1)
  })

  it('never starts rAF on mount when animated=false', () => {
    mountClock(false)
    expect(pendingCallbacks.size).toBe(0)
  })

  it('cancels rAF, disconnects IntersectionObserver, and cleans listeners on unmount', () => {
    mountClock(true)
    expect(pendingCallbacks.size).toBe(1)

    app?.unmount()
    app = null

    expect(cancelledIds).toEqual([1])
    expect(pendingCallbacks.size).toBe(0)
    expect(ioDisconnectSpy).toHaveBeenCalledTimes(1)
    expect(mqlListeners).toHaveLength(0)
  })

  it('pauses off-screen, on hidden tab, and under prefers-reduced-motion', () => {
    mountClock(true)
    expect(pendingCallbacks.size).toBe(1)

    ioCallbacks[0]?.([{ isIntersecting: false }])
    expect(pendingCallbacks.size).toBe(0)

    ioCallbacks[0]?.([{ isIntersecting: true }])
    expect(pendingCallbacks.size).toBe(1)

    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(pendingCallbacks.size).toBe(0)

    Object.defineProperty(document, 'hidden', { configurable: true, value: false })
    document.dispatchEvent(new Event('visibilitychange'))
    expect(pendingCallbacks.size).toBe(1)

    mqlMatches = true
    mqlListeners.forEach((listener) => listener())
    expect(pendingCallbacks.size).toBe(0)
  })
})
