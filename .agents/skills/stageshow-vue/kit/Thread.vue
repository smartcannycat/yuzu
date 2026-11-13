<script lang="ts">
import type { InjectionKey, Ref } from 'vue'

export interface ThreadContextValue {
  ready: Ref<boolean>
}

export const ThreadSymbol: InjectionKey<ThreadContextValue> = Symbol('ThreadContext')
</script>

<script setup lang="ts">
import {
  ref,
  provide,
  onMounted,
  onBeforeUpdate,
  onUpdated,
  type CSSProperties,
} from 'vue'
import './messages.css'

export interface ThreadProps {
  app?: 'imessage' | 'sms' | 'chat'
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<ThreadProps>(), {
  app: 'imessage',
})

const ready = ref(false)
provide(ThreadSymbol, { ready })

const root = ref<HTMLDivElement | null>(null)
let tops = new Map<Element, number>()

function threadTops(el: HTMLElement) {
  const style = getComputedStyle(el)
  const extra =
    style.boxSizing === 'border-box'
      ? 0
      : [style.paddingLeft, style.paddingRight, style.borderLeftWidth, style.borderRightWidth].reduce(
          (sum, value) => sum + (parseFloat(value) || 0),
          0,
        )
  const width = parseFloat(style.width) + extra
  const scale = (width && el.getBoundingClientRect().width / width) || 1
  const parents = new Map<Element, number>()
  return new Map(
    Array.from(el.children, (child) => {
      const parent = (child as HTMLElement).offsetParent
      if (parent && !parents.has(parent)) parents.set(parent, parent.getBoundingClientRect().top)
      return [child, (child.getBoundingClientRect().top - (parent ? parents.get(parent)! : 0)) / scale]
    }),
  )
}

function updateTails() {
  if (!root.value) return
  const rows = Array.from(root.value.querySelectorAll('.ss-bubble-row'))
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i] as HTMLElement
    const from = row.dataset.from
    const nextRow = rows[i + 1] as HTMLElement | undefined
    const isLastOfRun = !nextRow || nextRow.dataset.from !== from
    const bubble = row.querySelector('.ss-bubble')
    if (bubble) {
      if (!bubble.hasAttribute('data-manual-tail')) {
        bubble.toggleAttribute('data-tail', isLastOfRun)
      }
    }
  }
}

onBeforeUpdate(() => {
  if (root.value) tops = threadTops(root.value)
})

function flip() {
  if (!root.value) return
  const next = threadTops(root.value)
  for (const [node, top] of Array.from(next)) {
    const el = node as HTMLElement
    const was = tops.get(el)
    if (was === undefined || Math.abs(was - top) < 0.001) continue
    const now = parseFloat(getComputedStyle(el).top) || 0
    el.style.transition = 'none'
    el.style.top = `${was + now - top}px`
    void el.offsetWidth
    el.style.transition = ''
    el.style.top = ''
  }
  tops = next
  updateTails()
}

onMounted(() => {
  if (root.value) tops = threadTops(root.value)
  updateTails()
  ready.value = true
})

onUpdated(() => {
  flip()
})
</script>

<template>
  <div
    ref="root"
    :class="['ss-thread', props.className, props.class]"
    :data-app="props.app"
    :style="props.style"
  >
    <slot />
  </div>
</template>
