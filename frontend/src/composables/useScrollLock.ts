import {
  customRef,
  isRef,
  onScopeDispose,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

interface ElementLockState {
  count: number
  previousOverflow: string
}

const elementLockRegistry = new WeakMap<HTMLElement, ElementLockState>()

function acquireElementLock(el: HTMLElement | null | undefined): void {
  if (!el) return
  const existing = elementLockRegistry.get(el)
  if (existing) {
    existing.count += 1
    return
  }
  elementLockRegistry.set(el, {
    count: 1,
    previousOverflow: el.style.overflow,
  })
  el.style.overflow = 'hidden'
}

function releaseElementLock(el: HTMLElement | null | undefined): void {
  if (!el) return
  const existing = elementLockRegistry.get(el)
  if (!existing) return
  existing.count -= 1
  if (existing.count <= 0) {
    el.style.overflow = existing.previousOverflow
    elementLockRegistry.delete(el)
  }
}

export function getElementScrollLockCount(el: HTMLElement | null | undefined): number {
  if (!el) return 0
  return elementLockRegistry.get(el)?.count ?? 0
}

/**
 * Reference-counted body/element scroll lock safe for stacked BottomSheet or modal instances.
 * Accepts either a reactive boolean `Ref<boolean>` or a target element returning a writable lock ref.
 */
export function useScrollLock(active: Ref<boolean>): void
export function useScrollLock(
  target?: MaybeRefOrGetter<HTMLElement | null | undefined>,
  initialState?: boolean,
): Ref<boolean>
export function useScrollLock(
  targetOrActive?: Ref<boolean> | MaybeRefOrGetter<HTMLElement | null | undefined>,
  initialState = false,
): Ref<boolean> | void {
  if (isRef(targetOrActive) && typeof targetOrActive.value === 'boolean') {
    const activeRef = targetOrActive
    let lockedEl: HTMLElement | null = null

    watch(
      activeRef,
      (shouldLock) => {
        const body = typeof document !== 'undefined' ? document.body : null
        if (shouldLock && !lockedEl && body) {
          acquireElementLock(body)
          lockedEl = body
        } else if (!shouldLock && lockedEl) {
          releaseElementLock(lockedEl)
          lockedEl = null
        }
      },
      { immediate: true, flush: 'sync' },
    )

    onScopeDispose(() => {
      if (lockedEl) {
        releaseElementLock(lockedEl)
        lockedEl = null
      }
    })
    return
  }

  const targetGetter = targetOrActive as
    | MaybeRefOrGetter<HTMLElement | null | undefined>
    | undefined
  let isLocked = false
  let lockedEl: HTMLElement | null = null

  function resolveElement(): HTMLElement | null {
    if (targetGetter !== undefined) {
      return toValue(targetGetter) ?? null
    }
    return typeof document !== 'undefined' ? document.body : null
  }

  function applyLock(nextLocked: boolean): void {
    if (nextLocked === isLocked) return
    if (nextLocked) {
      const target = resolveElement()
      if (target) {
        acquireElementLock(target)
        lockedEl = target
      }
      isLocked = true
    } else {
      releaseElementLock(lockedEl)
      lockedEl = null
      isLocked = false
    }
  }

  if (initialState) {
    applyLock(true)
  }

  onScopeDispose(() => {
    applyLock(false)
  })

  return customRef<boolean>((track, trigger) => ({
    get() {
      track()
      return isLocked
    },
    set(value: boolean) {
      const next = Boolean(value)
      if (next !== isLocked) {
        applyLock(next)
        trigger()
      }
    },
  }))
}
