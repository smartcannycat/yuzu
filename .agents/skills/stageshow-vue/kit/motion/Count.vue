<script setup lang="ts">
import {
  ref,
  computed,
  watch,
  onMounted,
  nextTick,
  type CSSProperties,
} from 'vue'
import { useReducedMotion } from '../reduced-motion'
import './Count.css'

export interface CountProps {
  value: number
  format?: (n: number) => string
  duration?: number
  stagger?: number
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<CountProps>(), {
  format: (n: number) => Math.round(n).toLocaleString('en-US'),
  duration: 700,
  stagger: 45,
})

const STRIP = '012345678901234567890123456789'.split('')
const MIDDLE = 10

function unitOf(text: string) {
  const m = /^(.*\d)(\s*)([^\d\s.,]+)$/.exec(text)
  return m ? { head: m[1], space: m[2].length > 0, unit: m[3] } : { head: text, space: false, unit: '' }
}

function digitsFromRight(text: string) {
  const out: number[] = []
  for (let i = text.length - 1; i >= 0; i--) {
    const c = text[i]
    if (c >= '0' && c <= '9') out.push(Number(c))
  }
  return out
}

const reduced = useReducedMotion()
const el = ref<HTMLSpanElement | null>(null)
const text = computed(() => props.format(props.value))
const unitData = computed(() => unitOf(text.value))
const digits = computed(() => digitsFromRight(text.value))

const idx = ref<number[]>(digits.value.map((d) => MIDDLE + d))
let prevInfo = { text: text.value, value: props.value, idx: [...idx.value] }
let homing = false
let settleTimer = 0

watch(
  () => [text.value, props.value],
  ([nextText, nextValue]) => {
    const node = el.value
    if (!node) return
    const prev = prevInfo
    if (prev.text === nextText) return
    const instant = reduced.value || props.duration <= 0 || !!node.closest('[data-instant], [data-offscreen]')
    const before = digitsFromRight(prev.text)
    const currentDigits = digits.value
    const up = (nextValue as number) >= prev.value
    const next = currentDigits.map((d, c) => {
      const was = before[c]
      const at = prev.idx[c]
      if (was === undefined || at === undefined || instant) return MIDDLE + d
      if (was === d) return at
      return up ? at + ((d - was + 10) % 10) : at - ((was - d + 10) % 10)
    })
    node.toggleAttribute('data-snap', instant)
    if (!instant) {
      for (const strip of Array.from(node.querySelectorAll<HTMLElement>('.ss-count__strip'))) {
        void getComputedStyle(strip).transform
      }
      node.setAttribute('data-rolling', '')
    }
    prevInfo = { text: nextText as string, value: nextValue as number, idx: next }
    idx.value = next

    clearTimeout(settleTimer)
    settleTimer = window.setTimeout(() => {
      node.setAttribute('data-snap', '')
      homing = true
      const home = currentDigits.map((d) => MIDDLE + d)
      prevInfo.idx = home
      idx.value = home
      node.removeAttribute('data-rolling')
      nextTick(() => {
        if (!homing) return
        homing = false
        for (const strip of Array.from(node.querySelectorAll<HTMLElement>('.ss-count__strip'))) {
          void getComputedStyle(strip).transform
        }
        node.removeAttribute('data-snap')
      })
    }, props.duration + props.stagger * currentDigits.length + 60)
  },
)

const items = computed(() => {
  const chars = unitData.value.head.split('')
  let fromRight = digits.value.length
  return chars.map((c, i) => {
    if (c < '0' || c > '9') {
      return { type: 'char' as const, key: `s${i}-${c}`, char: c }
    }
    const column = --fromRight
    const at = idx.value[column] ?? MIDDLE + Number(c)
    return { type: 'digit' as const, key: `d${column}`, column, at }
  })
})
</script>

<template>
  <span
    ref="el"
    :class="['ss-count', props.className, props.class]"
    :style="props.style"
    :aria-label="text"
    v-bind="$attrs"
  >
    <template v-for="item in items" :key="item.key">
      <span v-if="item.type === 'char'" class="ss-count__char" aria-hidden="true">
        {{ item.char }}
      </span>
      <span v-else class="ss-count__digit" data-crop aria-hidden="true">
        <span
          class="ss-count__strip"
          :style="{
            transform: `translateY(${-item.at}em)`,
            transitionDuration: `${props.duration}ms`,
            transitionDelay: `${item.column * props.stagger}ms`,
          }"
        >
          <span v-for="(n, k) in STRIP" :key="k">{{ n }}</span>
        </span>
      </span>
    </template>
    <span
      v-if="unitData.unit"
      class="ss-count__unit"
      :data-space="unitData.space || undefined"
      aria-hidden="true"
    >
      {{ unitData.unit }}
    </span>
  </span>
</template>
