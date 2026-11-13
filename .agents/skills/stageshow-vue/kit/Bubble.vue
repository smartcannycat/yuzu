<script setup lang="ts">
import {
  ref,
  computed,
  inject,
  isVNode,
  onMounted,
  onUpdated,
  watch,
  useSlots,
  type CSSProperties,
} from 'vue'
import { useLook } from './looks'
import { ThreadSymbol } from './Thread.vue'
import './messages.css'

defineOptions({ inheritAttrs: false })

export interface BubbleProps {
  from: 'me' | 'them'
  typing?: boolean
  tail?: boolean
  source?: string
  tapback?: { emoji: any; show?: boolean }
  avatar?: any
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<BubbleProps>(), {
  typing: false,
})

const slots = useSlots()
const look = useLook()
const thread = inject(ThreadSymbol, null)
const arrived = ref(Boolean(thread?.ready.value))

const bubbleRef = ref<HTMLDivElement | null>(null)
let prevSize: { w: number; h: number } | null = null
const wasTyping = ref(props.typing)
const grew = ref(false)

if (wasTyping.value && !props.typing) grew.value = true
wasTyping.value = props.typing

function isRenderableObject(v: any): boolean {
  return isVNode(v) || typeof v === 'function' || (typeof v === 'object' && v !== null)
}

function asComponent(v: any) {
  if (typeof v === 'function') return v
  if (isVNode(v) || Array.isArray(v)) return () => v
  return v
}

function getSlotText(vnodes?: any[]): string {
  if (!vnodes) return ''
  let s = ''
  for (const n of vnodes) {
    if (typeof n === 'string' || typeof n === 'number') s += n
    else if (typeof n?.children === 'string') s += n.children
    else if (Array.isArray(n?.children)) s += getSlotText(n.children)
  }
  return s
}

const minimalBarWidth = computed(() => {
  const txt = getSlotText(slots.default?.())
  return Math.min(180, (txt.length || 16) * 5.5)
})

const isPlainStringSlot = computed(() => {
  const vnodes = slots.default?.()
  if (!vnodes || vnodes.length !== 1) return false
  const n = vnodes[0]
  return typeof n === 'string' || typeof n?.children === 'string'
})

function morphSize() {
  const el = bubbleRef.value
  if (!el) return
  const was = prevSize
  el.style.width = ''
  el.style.height = ''
  const measured = getComputedStyle(el)
  const now = { w: parseFloat(measured.width), h: parseFloat(measured.height) }
  prevSize = now
  if (!was || (was.w === now.w && was.h === now.h)) return

  const text = el.querySelector<HTMLElement>('.ss-bubble__text')
  if (text) text.style.width = getComputedStyle(text).width
  el.style.transition = 'none'
  el.style.width = `${was.w}px`
  el.style.height = `${was.h}px`
  void el.offsetWidth
  el.style.transition = ''
  el.style.width = `${now.w}px`
  el.style.height = `${now.h}px`

  const end = () => {
    el.style.width = ''
    el.style.height = ''
    if (text) text.style.width = ''
  }
  el.addEventListener('transitionend', end, { once: true })
}

onMounted(() => {
  const el = bubbleRef.value
  if (!el) return
  const measured = getComputedStyle(el)
  prevSize = { w: parseFloat(measured.width), h: parseFloat(measured.height) }

  // Form out of composer
  if (arrived.value && props.source) {
    const stage = el.closest('.ss-stage') ?? document
    const src =
      stage.querySelector<HTMLElement>(`[data-target="${props.source}"]`) ??
      stage.querySelector<HTMLElement>(props.source)
    const text = el.querySelector<HTMLElement>('.ss-bubble__text')
    if (src && text) {
      if (
        !window.matchMedia('(prefers-reduced-motion: reduce)').matches &&
        !el.closest('[data-still]')
      ) {
        el.style.transition = 'none'
        el.style.left = el.style.top = '0px'
        const k = el.getBoundingClientRect().width / el.offsetWidth || 1
        const o = src.getBoundingClientRect()
        const t = text.getBoundingClientRect()
        const dx = (o.left - t.left) / k
        const dy = (o.top + o.height / 2 - (t.top + t.height / 2)) / k
        const ease = 'cubic-bezier(0.22, 1, 0.36, 1)'

        el.style.transition = 'none'
        el.style.left = `${dx}px`
        el.style.top = `${dy}px`
        el.setAttribute('data-flying', '')
        el.style.color = getComputedStyle(src).color
        void el.offsetWidth
        el.style.transition = `left 0.5s ${ease}, top 0.5s ${ease}, color 0.3s ease 0.06s`
        el.style.left = el.style.top = ''
        el.removeAttribute('data-flying')
        el.style.color = ''

        const end = (e: TransitionEvent) => {
          if (e.target !== el || e.propertyName !== 'top') return
          el.style.transition = ''
          el.removeEventListener('transitionend', end)
        }
        el.addEventListener('transitionend', end)
      }
    }
  }
})

watch(
  () => props.typing,
  (next) => {
    if (wasTyping.value && !next) grew.value = true
    wasTyping.value = next
  },
)

onUpdated(() => {
  morphSize()
})

const hasAvatar = computed(() => Boolean(props.avatar || slots.avatar))
</script>

<template>
  <div
    :class="['ss-bubble-row', props.className, props.class]"
    :data-from="props.from"
    :data-avatar="hasAvatar ? '' : undefined"
    :style="props.style"
  >
    <span v-if="hasAvatar && props.from !== 'me'" class="ss-bubble__avatar" aria-hidden="true">
      <slot name="avatar">
        <component :is="asComponent(props.avatar)" v-if="isRenderableObject(props.avatar)" />
        <template v-else>{{ props.avatar }}</template>
      </slot>
    </span>

    <div
      ref="bubbleRef"
      class="ss-bubble"
      :data-arrived="arrived || undefined"
      :data-source="props.source ? '' : undefined"
      :data-tail="props.tail || undefined"
      :data-manual-tail="props.tail !== undefined ? '' : undefined"
      :data-typing="props.typing || undefined"
      :data-grew="grew || undefined"
      :data-tapback="props.tapback && props.tapback.show !== false ? '' : undefined"
      v-bind="$attrs"
    >
      <span
        v-if="props.tapback"
        class="ss-tapback"
        :data-show="props.tapback.show !== false || undefined"
        aria-hidden="true"
      >
        <span class="ss-tapback__emoji">
          <component :is="asComponent(props.tapback!.emoji)" v-if="isRenderableObject(props.tapback.emoji)" />
          <template v-else>{{ props.tapback.emoji }}</template>
        </span>
      </span>

      <span v-if="props.typing" class="ss-bubble__dots" aria-label="typing">
        <i />
        <i />
        <i />
      </span>

      <span v-else class="ss-bubble__text">
        <span
          v-if="look.fidelity === 'minimal' && isPlainStringSlot"
          class="ss-bar ss-bubble__bar"
          :style="{ width: `${minimalBarWidth}px` }"
        />
        <slot v-else />
      </span>

      <svg class="ss-bubble__tail" viewBox="0 0 18 16" aria-hidden="true">
        <path
          :d="
            props.from === 'me'
              ? 'M0 0H12V8.5C12 12.6 14 15 17.5 16C15 16.7 12.2 16.5 9.8 15.3L0 15Z'
              : 'M18 0H6V8.5C6 12.6 4 15 0.5 16C3 16.7 5.8 16.5 8.2 15.3L18 15Z'
          "
        />
      </svg>
    </div>
  </div>
</template>
