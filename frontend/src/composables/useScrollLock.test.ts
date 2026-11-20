import { afterEach, describe, expect, it } from 'vitest'
import { effectScope, ref } from 'vue'

import { getElementScrollLockCount, useScrollLock } from '@/composables/useScrollLock'

describe('useScrollLock', () => {
  afterEach(() => {
    document.body.style.overflow = ''
  })

  it('reference-counts stacked element locks without unlocking while another instance remains active', () => {
    document.body.style.overflow = 'auto'

    const scopeA = effectScope()
    const lockA = scopeA.run(() => useScrollLock(document.body))!

    const scopeB = effectScope()
    const lockB = scopeB.run(() => useScrollLock(document.body))!

    lockA.value = true
    expect(document.body.style.overflow).toBe('hidden')
    expect(getElementScrollLockCount(document.body)).toBe(1)

    // Idempotent duplicate set(true)
    lockA.value = true
    expect(getElementScrollLockCount(document.body)).toBe(1)

    lockB.value = true
    expect(getElementScrollLockCount(document.body)).toBe(2)
    expect(document.body.style.overflow).toBe('hidden')

    // Closing A keeps body locked because B is still open
    lockA.value = false
    expect(getElementScrollLockCount(document.body)).toBe(1)
    expect(document.body.style.overflow).toBe('hidden')

    // Unmounting B while locked restores original overflow
    scopeB.stop()
    expect(getElementScrollLockCount(document.body)).toBe(0)
    expect(document.body.style.overflow).toBe('auto')

    scopeA.stop()
  })

  it('supports reactive boolean Ref<boolean> mode cleanly', () => {
    const activeA = ref(true)
    const activeB = ref(true)

    const scopeA = effectScope()
    scopeA.run(() => useScrollLock(activeA))
    expect(document.body.style.overflow).toBe('hidden')
    expect(getElementScrollLockCount(document.body)).toBe(1)

    const scopeB = effectScope()
    scopeB.run(() => useScrollLock(activeB))
    expect(getElementScrollLockCount(document.body)).toBe(2)

    activeA.value = false
    expect(getElementScrollLockCount(document.body)).toBe(1)
    expect(document.body.style.overflow).toBe('hidden')

    activeB.value = false
    expect(getElementScrollLockCount(document.body)).toBe(0)
    expect(document.body.style.overflow).toBe('')

    scopeA.stop()
    scopeB.stop()
  })
})
