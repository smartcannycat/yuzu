import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, ref } from 'vue'

import BatchUploadSheet from '@/components/lots/BatchUploadSheet.vue'
import * as batchDemoModule from '@/utils/batchDemo'

async function flushUi(): Promise<void> {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('BatchUploadSheet', () => {
  let host: HTMLDivElement | null = null
  let app: ReturnType<typeof createApp> | null = null

  beforeEach(() => {
    let counter = 0
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
      counter += 1
      return `blob:mock-preview/${counter}`
    })
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
  })

  afterEach(() => {
    app?.unmount()
    host?.remove()
    app = null
    host = null
    vi.restoreAllMocks()
  })

  async function mountSheet(options: { serverError?: string | null; maxFiles?: number } = {}) {
    const open = ref(true)
    const onSubmit = vi.fn()
    host = document.createElement('div')
    document.body.appendChild(host)

    app = createApp({
      components: { BatchUploadSheet },
      setup() {
        return {
          open,
          maxFiles: options.maxFiles ?? 10,
          serverError: options.serverError ?? null,
          onSubmit,
        }
      },
      template:
        '<BatchUploadSheet v-model:open="open" :max-files="maxFiles" :server-error="serverError" @submit="onSubmit" />',
    })
    app.mount(host)
    await flushUi()
    return { open, onSubmit }
  }

  it('stages valid files, revokes preview URL on removal, rejects 0-byte files, and emits submit', async () => {
    const { onSubmit } = await mountSheet()
    const fileInput = document.body.querySelector(
      'input[aria-label="Выбрать файлы аукционных листов"]',
    ) as HTMLInputElement
    expect(fileInput).not.toBeNull()

    const validFile = new File(['abc'], 'sheet_1.jpg', { type: 'image/jpeg' })
    Object.defineProperty(fileInput, 'files', {
      configurable: true,
      value: [validFile],
    })
    fileInput.dispatchEvent(new Event('change'))
    await vi.waitFor(() => {
      expect(document.body.textContent).toContain('Выбрано 1 из 10')
    })
    expect(document.body.textContent).toContain('sheet_1.jpg')

    // Reject 0-byte empty file cleanly
    const emptyFile = new File([], 'empty.jpg', { type: 'image/jpeg' })
    Object.defineProperty(fileInput, 'files', {
      configurable: true,
      value: [emptyFile],
    })
    fileInput.dispatchEvent(new Event('change'))
    await vi.waitFor(() => {
      const alert = document.body.querySelector('[role="alert"]')
      expect(alert?.textContent).toContain('Пустой')
    })

    // Submit staged valid file
    const submitBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Запустить расчёт'),
    )
    submitBtn?.click()
    await flushUi()
    expect(onSubmit).toHaveBeenCalledWith([validFile])

    // Remove staged file -> revokes preview URL
    const removeBtn = document.body.querySelector(
      'button[aria-label="Удалить файл sheet_1.jpg"]',
    ) as HTMLButtonElement
    removeBtn.click()
    await flushUi()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-preview/1')
  })

  it('catches demo sheet generation errors cleanly without unhandled rejection', async () => {
    vi.spyOn(batchDemoModule, 'createDemoAuctionSheetFiles').mockRejectedValue(
      new Error('Canvas недоступен'),
    )
    await mountSheet()

    const demoBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Демо-листы'),
    )
    expect(demoBtn).toBeTruthy()
    demoBtn!.click()
    await vi.waitFor(() => {
      const alert = document.body.querySelector('[role="alert"]')
      expect(alert?.textContent).toContain('Canvas недоступен')
    })
  })
})
