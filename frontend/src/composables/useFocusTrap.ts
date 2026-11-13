import { onKeyStroke } from '@vueuse/core'
import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true',
  )
}

/**
 * Traps keyboard Tab navigation inside a container while active
 * and restores focus to the trigger element when deactivated.
 */
export function useFocusTrap(containerRef: Ref<HTMLElement | null>, active: Ref<boolean>) {
  let previousFocus: HTMLElement | null = null

  function restoreFocus() {
    if (previousFocus && document.contains(previousFocus)) {
      previousFocus.focus()
    }
    previousFocus = null
  }

  watch(
    active,
    async (isActive) => {
      if (isActive) {
        previousFocus =
          document.activeElement instanceof HTMLElement ? document.activeElement : null
        await nextTick()
        const container = containerRef.value
        if (!container) return

        const focusables = getFocusableElements(container)
        const target = focusables[0] ?? container
        target.focus()
      } else {
        restoreFocus()
      }
    },
    { flush: 'post' },
  )

  onKeyStroke(
    'Tab',
    (event) => {
      if (!active.value) return
      const container = containerRef.value
      if (!container) return

      const focusables = getFocusableElements(container)
      if (focusables.length === 0) {
        event.preventDefault()
        container.focus()
        return
      }

      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      if (!first || !last) return

      const current = document.activeElement
      if (event.shiftKey) {
        if (current === first || !container.contains(current)) {
          event.preventDefault()
          last.focus()
        }
      } else if (current === last || !container.contains(current)) {
        event.preventDefault()
        first.focus()
      }
    },
    { target: typeof window !== 'undefined' ? window : undefined },
  )

  onBeforeUnmount(() => {
    if (active.value) {
      restoreFocus()
    }
  })
}
