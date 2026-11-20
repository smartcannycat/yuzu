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

function isScreenReaderOnly(el: HTMLElement): boolean {
  return el.classList.contains('sr-only') || el.classList.contains('visually-hidden')
}

function hasZeroBox(rect: DOMRect): boolean {
  return rect.width <= 0 && rect.height <= 0
}

function isElementVisibleForFocus(
  el: HTMLElement,
  container: HTMLElement,
  hasLayoutEngine: boolean,
): boolean {
  if (el.hasAttribute('disabled') || el.getAttribute('aria-hidden') === 'true') {
    return false
  }
  if (el.closest('[hidden], [inert], [aria-hidden="true"]')) {
    return false
  }

  if (typeof window !== 'undefined' && typeof window.getComputedStyle === 'function') {
    let cursor: HTMLElement | null = el
    while (cursor) {
      const style = window.getComputedStyle(cursor)
      if (style.display === 'none') {
        return false
      }
      if (cursor === el && (style.visibility === 'hidden' || style.visibility === 'collapse')) {
        return false
      }
      if (cursor === container) break
      cursor = cursor.parentElement
    }

    const ownStyle = window.getComputedStyle(el)
    if (ownStyle.visibility === 'hidden' || ownStyle.visibility === 'collapse') {
      return false
    }
    if (!isScreenReaderOnly(el) && ownStyle.width === '0px' && ownStyle.height === '0px') {
      return false
    }
  }

  if (hasLayoutEngine && !isScreenReaderOnly(el)) {
    const rect = el.getBoundingClientRect()
    if (hasZeroBox(rect)) {
      return false
    }
  }

  return true
}

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const candidates = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
  if (candidates.length === 0) return []

  const containerRect = container.getBoundingClientRect()
  const hasLayoutEngine =
    !hasZeroBox(containerRect) ||
    candidates.some((candidate) => !hasZeroBox(candidate.getBoundingClientRect()))

  return candidates.filter((el) => isElementVisibleForFocus(el, container, hasLayoutEngine))
}

/**
 * Traps keyboard Tab navigation inside a container while active
 * and restores focus to the trigger element when deactivated.
 */
export function useFocusTrap(containerRef: Ref<HTMLElement | null>, active: Ref<boolean>) {
  let previousFocus: HTMLElement | null = null
  let isDisposed = false

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
        if (isDisposed || !active.value) return
        const container = containerRef.value
        if (!container) return

        const focusables = getFocusableElements(container)
        const target = focusables[0] ?? container
        target.focus()
      } else {
        restoreFocus()
      }
    },
    { flush: 'post', immediate: true },
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
    isDisposed = true
    if (active.value) {
      restoreFocus()
    }
  })
}
