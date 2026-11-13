<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots, watch } from 'vue'
import { useReducedMotion } from '../reduced-motion'
import './Roll.css'

export interface RollProps {
  /** The text or number to display (or pass as default slot). */
  text?: string | number
  /** Hold the old text this many ms before rolling: a total that changes
   * after the row that caused it has landed, not on the same frame. */
  delay?: number
  stagger?: number
  /** The side the text is pinned to. Found from the layout when left out: a
   * right-aligned value (text-align right, or last in a space-between or
   * flex-end row) changes against its right edge, so it never drifts. */
  align?: 'start' | 'end'
  /** 'roll' slides text up through the line, for numbers and inline text. 'fade'
   * crossfades in place with a small lift, for labels on buttons and other
   * controls, where a full roll shows two lines at once. */
  variant?: 'roll' | 'fade'
  class?: any
  style?: any
}

const props = withDefaults(defineProps<RollProps>(), {
  delay: 0,
  stagger: 45,
  variant: 'roll',
})

const slots = useSlots()

function getSlotText(vnodes: any[]): string {
  let s = ''
  for (const n of vnodes) {
    if (typeof n === 'string' || typeof n === 'number') s += n
    else if (typeof n?.children === 'string') s += n.children
    else if (Array.isArray(n?.children)) s += getSlotText(n.children)
  }
  return s
}

const rawText = computed(() => {
  if (props.text !== undefined) return String(props.text)
  if (slots.default) return getSlotText(slots.default())
  return ''
})

const reduced = useReducedMotion()
const delayedText = ref(rawText.value)
let delayTimer: ReturnType<typeof setTimeout> | null = null

watch(rawText, (val) => {
  if (delayTimer) clearTimeout(delayTimer)
  if (!props.delay || reduced.value) {
    delayedText.value = val
    return
  }
  delayTimer = setTimeout(() => {
    delayedText.value = val
  }, props.delay)
}, { immediate: true })

const view = ref({
  text: delayedText.value,
  head: 0,
  tail: 0,
  old: '',
  key: 0,
  numeric: true,
})

const mid = ref<HTMLSpanElement | null>(null)
const root = ref<HTMLSpanElement | null>(null)
const fromWidth = ref<number | null>(null)
const side = ref<'start' | 'end'>(props.align ?? 'start')

function rootWidth() {
  if (!root.value || !mid.value) return 0
  const height = parseFloat(getComputedStyle(mid.value).height)
  const scale = height > 0 ? mid.value.getBoundingClientRect().height / height : 1
  return root.value.getBoundingClientRect().width / (scale || 1)
}

function updateSide() {
  if (props.align) {
    side.value = props.align
    return
  }
  const el = root.value
  if (!el?.parentElement) return
  let box: HTMLElement = el
  while (box.parentElement && box.parentElement.childElementCount === 1 && Math.abs(box.parentElement.getBoundingClientRect().width - box.getBoundingClientRect().width) < 1) {
    box = box.parentElement
  }
  const parent = box.parentElement
  if (!parent) return
  const p = getComputedStyle(parent)
  const flex = /flex/.test(p.display) && p.flexDirection.startsWith('row')
  const pushed = () => {
    const prev = box.previousElementSibling
    const r = box.getBoundingClientRect()
    const pr = parent.getBoundingClientRect()
    const flush = Math.abs(pr.right - parseFloat(p.paddingRight) - parseFloat(p.borderRightWidth) - r.right) < 1
    const slack = prev ? r.left - prev.getBoundingClientRect().right - (parseFloat(p.columnGap) || 0) : 0
    return flush && slack > 1
  }
  const end =
    /right|end/.test(getComputedStyle(el).textAlign) ||
    (flex && box === parent.lastElementChild && (/space-between|flex-end|^end/.test(p.justifyContent) || pushed()))
  side.value = end ? 'end' : 'start'
}

onMounted(() => {
  updateSide()
})

watch(() => props.align, () => {
  updateSide()
})

let clearOldTimer: ReturnType<typeof setTimeout> | null = null
let widestTimer: ReturnType<typeof setTimeout> | null = null

watch(delayedText, (newText) => {
  if (reduced.value) {
    view.value = { text: newText, head: 0, tail: 0, old: '', key: 0, numeric: true }
    return
  }
  if (view.value.text === newText) return
  const a = view.value.text
  const b = newText
  let head = 0
  while (head < a.length && head < b.length && a[head] === b[head]) head++
  let tail = 0
  while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++

  const numeric = /^[\d.,$€£%+\-−\s]*$/.test(a.slice(head, a.length - tail) + b.slice(head, b.length - tail))
  if (!numeric) {
    const space = (c: string | undefined) => c === undefined || /\s/.test(c)
    while (head > 0 && !space(b[head - 1]) && !space(b[head])) head--
    while (tail > 0 && !space(b[b.length - tail - 1]) && !space(b[b.length - tail])) tail--
  }

  const nextKey = view.value.key + 1
  fromWidth.value = rootWidth()
  view.value = {
    text: b,
    head,
    tail,
    old: a.slice(head, a.length - tail),
    key: nextKey,
    numeric,
  }

  if (clearOldTimer) clearTimeout(clearOldTimer)
  clearOldTimer = setTimeout(() => {
    if (view.value.key === nextKey) {
      view.value.old = ''
    }
  }, 700)

  nextTick(() => {
    applySizing()
  })
})

function applySizing() {
  const el = mid.value
  const live = el?.querySelector<HTMLElement>('[data-live]')
  const out = el?.querySelector<HTMLElement>('[data-out]')
  if (!el || !live) return
  const width = (node: HTMLElement) => parseFloat(getComputedStyle(node).width) || 0
  const next = width(live)
  if (reduced.value || view.value.key === 0) {
    el.style.transition = 'none'
    el.style.width = `${next}px`
    fromWidth.value = null
    return
  }
  const affixes = rootWidth() - width(el)
  const previous = fromWidth.value
  fromWidth.value = null
  const start = previous === null ? (out ? width(out) : 0) : Math.max(0, previous - affixes)
  el.style.transition = 'none'
  el.style.width = `${start}px`
  void el.offsetWidth
  el.style.transition = ''

  if (props.variant === 'fade') {
    el.style.width = `${next}px`
    return
  }
  const widest = Math.max(next, start, out ? width(out) : 0)
  el.style.width = `${widest}px`
  if (widest === next) return
  if (widestTimer) clearTimeout(widestTimer)
  widestTimer = setTimeout(() => {
    el.style.width = `${next}px`
  }, 360)
}

onBeforeUnmount(() => {
  if (delayTimer) clearTimeout(delayTimer)
  if (clearOldTimer) clearTimeout(clearOldTimer)
  if (widestTimer) clearTimeout(widestTimer)
})

const activeView = computed(() => {
  return reduced.value
    ? { text: delayedText.value, head: 0, tail: 0, old: '', key: 0, numeric: true }
    : view.value
})

const now = computed(() => {
  const { text, head, tail } = activeView.value
  return text.slice(head, text.length - tail)
})

const units = computed(() => {
  return activeView.value.numeric ? now.value.split('') : now.value.split(/(?<=\s)/)
})
</script>

<template>
  <span
    ref="root"
    class="ss-roll"
    :class="props.class"
    :data-variant="props.variant"
    :data-align="side"
    :style="props.style"
    v-bind="$attrs"
  >
    {{ activeView.text.slice(0, activeView.head) }}
    <span ref="mid" class="ss-roll__mid">
      <span v-if="activeView.old" :key="`o${activeView.key}`" class="ss-roll__item" data-out>
        {{ activeView.old }}
      </span>
      <span :key="`n${activeView.key}`" class="ss-roll__item" data-live>
        <span v-if="activeView.key > 0 && props.variant === 'fade'" class="ss-roll__char">
          {{ now }}
        </span>
        <template v-else-if="activeView.key > 0">
          <span
            v-for="(c, i) in units"
            :key="i"
            class="ss-roll__char"
            :style="{ animationDelay: `${110 + i * props.stagger}ms` }"
          >
            {{ c }}
          </span>
        </template>
        <template v-else>
          {{ now }}
        </template>
      </span>
    </span>
    {{ activeView.text.slice(activeView.text.length - activeView.tail) }}
  </span>
</template>
