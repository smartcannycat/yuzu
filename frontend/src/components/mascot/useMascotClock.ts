import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  toValue,
  watch,
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

export interface MascotClockOptions {
  root?: Ref<HTMLElement | null>
  animated?: MaybeRefOrGetter<boolean>
}

export interface MascotClock {
  root: Ref<HTMLElement | null>
  now: Ref<number>
  t0: Ref<number>
  reduced: Ref<boolean>
  isAnimated: ComputedRef<boolean>
  isActive: ComputedRef<boolean>
  start: () => void
  stop: () => void
}

function isDocumentHidden(): boolean {
  return typeof document !== 'undefined' && document.hidden
}

/**
 * Shared animation clock managing a single requestAnimationFrame loop paused
 * off-screen (IntersectionObserver), on hidden tabs, under reduced motion, or
 * when reactive `animated` becomes false.
 */
export function useMascotClock(options: MascotClockOptions = {}): MascotClock {
  const root = options.root ?? ref<HTMLElement | null>(null)
  const initialNow = performance.now()
  const now = ref(initialNow)
  const t0 = ref(initialNow)
  const reduced = ref(false)

  const isAnimated = computed(() =>
    options.animated === undefined ? true : Boolean(toValue(options.animated)),
  )
  const isActive = computed(() => isAnimated.value && !reduced.value)

  let raf = 0
  let onScreen = true
  let isMounted = false
  let isUnmounted = false
  let mql: MediaQueryList | null = null
  let io: IntersectionObserver | null = null

  function canRun(): boolean {
    return (
      isMounted &&
      !isUnmounted &&
      isAnimated.value &&
      !reduced.value &&
      onScreen &&
      !isDocumentHidden()
    )
  }

  function stop(): void {
    if (raf) {
      cancelAnimationFrame(raf)
      raf = 0
    }
  }

  function frame(ts: number): void {
    if (!canRun()) {
      raf = 0
      return
    }
    now.value = ts
    raf = requestAnimationFrame(frame)
  }

  function start(): void {
    if (raf || !canRun()) return
    raf = requestAnimationFrame(frame)
  }

  function onVisibility(): void {
    if (isDocumentHidden()) stop()
    else start()
  }

  function onReducedChange(): void {
    reduced.value = Boolean(mql?.matches)
    if (reduced.value) {
      stop()
      now.value = performance.now()
    } else {
      start()
    }
  }

  watch(
    isAnimated,
    (nextAnimated) => {
      if (!nextAnimated) {
        stop()
        now.value = performance.now()
        return
      }
      if (isMounted && !isUnmounted && !reduced.value) {
        const ts = performance.now()
        t0.value = ts
        now.value = ts
        start()
      }
    },
    { flush: 'sync' },
  )

  onMounted(() => {
    isMounted = true
    const ts = performance.now()
    t0.value = ts
    now.value = ts

    if (typeof window !== 'undefined') {
      mql = window.matchMedia?.('(prefers-reduced-motion: reduce)') ?? null
      reduced.value = Boolean(mql?.matches)
      mql?.addEventListener?.('change', onReducedChange)

      if ('IntersectionObserver' in window && root.value) {
        io = new IntersectionObserver(([entry]) => {
          if (isUnmounted) return
          onScreen = Boolean(entry?.isIntersecting)
          if (onScreen) start()
          else stop()
        })
        io.observe(root.value)
      }
    }

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibility)
    }

    start()
  })

  onBeforeUnmount(() => {
    isUnmounted = true
    stop()
    io?.disconnect()
    io = null
    mql?.removeEventListener?.('change', onReducedChange)
    mql = null
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibility)
    }
  })

  return {
    root,
    now,
    t0,
    reduced,
    isAnimated,
    isActive,
    start,
    stop,
  }
}
