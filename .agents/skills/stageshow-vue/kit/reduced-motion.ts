import { inject, provide, ref, onMounted, onUnmounted, computed, type InjectionKey, type Ref, type ComputedRef } from 'vue'

// Static stages settle motion parts too, even without an OS preference.
export const StillSymbol: InjectionKey<Ref<boolean>> = Symbol('StillContext')

export function provideStill(still: Ref<boolean>) {
  provide(StillSymbol, still)
}

/** Whether the viewer asked for reduced motion. A stage shows its still; parts skip their tweens. */
export function useReducedMotion(): ComputedRef<boolean> {
  const still = inject(StillSymbol, ref(false))
  const reduced = ref(false)

  if (typeof window !== 'undefined' && window.matchMedia) {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    reduced.value = mq.matches
    const update = () => {
      reduced.value = mq.matches
    }
    onMounted(() => {
      mq.addEventListener('change', update)
    })
    onUnmounted(() => {
      mq.removeEventListener('change', update)
    })
  }

  return computed(() => Boolean(still.value || reduced.value))
}
