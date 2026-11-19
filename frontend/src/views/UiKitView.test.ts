import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import UiKitView from '@/views/UiKitView.vue'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
}

describe('UiKitView', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('clears pending loading demo timer on unmount', async () => {
    const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout')
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: { template: '<div />' } },
        { path: '/ui-kit', name: 'ui-kit', component: UiKitView },
      ],
    })
    await router.push('/ui-kit')
    await router.isReady()

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(UiKitView)
    app.use(router)
    app.mount(host)
    await flushUi()

    const calcBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Рассчитать под ключ'),
    )
    expect(calcBtn).toBeTruthy()
    calcBtn!.click()
    await flushUi()
    expect(host.textContent).toContain('Пересчёт...')

    app.unmount()
    app = null
    expect(clearTimeoutSpy).toHaveBeenCalled()
  })
})
