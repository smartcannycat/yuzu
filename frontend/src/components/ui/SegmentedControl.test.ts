import { afterEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, ref } from 'vue'

import SegmentedControl, { type SegmentOption } from '@/components/ui/SegmentedControl.vue'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('SegmentedControl', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
  })

  it('clears stale tabRefs on option list shrink and handles keyboard navigation cleanly', async () => {
    const active = ref<'a' | 'b' | 'c'>('a')
    const options = ref<SegmentOption<'a' | 'b' | 'c'>[]>([
      { value: 'a', label: 'Первый' },
      { value: 'b', label: 'Второй' },
      { value: 'c', label: 'Третий' },
    ])

    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp({
      components: { SegmentedControl },
      setup: () => ({ active, options }),
      template:
        '<SegmentedControl v-model="active" :options="options" aria-label="Тест вкладок" />',
    })
    app.mount(host)
    await flushUi()

    expect(host.querySelectorAll('[role="tab"]').length).toBe(3)

    // Shrink options from 3 tabs to 2 tabs; onBeforeUpdate must purge stale 3rd ref
    options.value = [
      { value: 'a', label: 'Первый' },
      { value: 'b', label: 'Второй' },
    ]
    await flushUi()

    const tabs = Array.from(host.querySelectorAll('[role="tab"]')) as HTMLButtonElement[]
    expect(tabs.length).toBe(2)

    tabs[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
    await flushUi()
    expect(active.value).toBe('b')

    // Wrapping past end lands on index 0 without touching stale removed ref at index 2
    tabs[1]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
    await flushUi()
    expect(active.value).toBe('a')

    tabs[0]!.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }))
    await flushUi()
    expect(active.value).toBe('b')
  })
})
