<script setup lang="ts" generic="T extends string | number">
import { useResizeObserver } from '@vueuse/core'
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'

export interface SegmentOption<Value extends string | number = string> {
  value: Value
  label: string
  badge?: string | number
  disabled?: boolean
}

interface Props {
  options: SegmentOption<T>[]
  ariaLabel: string
  fullWidth?: boolean
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  fullWidth: false,
  size: 'md',
})

const modelValue = defineModel<T>({ required: true })

const listRef = useTemplateRef<HTMLDivElement>('listRef')
const pillRef = useTemplateRef<HTMLSpanElement>('pillRef')
const tabRefs = ref<HTMLButtonElement[]>([])

const activeIndex = computed(() =>
  props.options.findIndex((option) => option.value === modelValue.value),
)

function moveIndicator(animate: boolean) {
  const pill = pillRef.value
  const activeButton = tabRefs.value[activeIndex.value]
  if (!pill || !activeButton) {
    if (pill) {
      pill.style.opacity = '0'
      pill.style.width = '0px'
    }
    return
  }

  const applyPosition = () => {
    pill.style.width = `${activeButton.offsetWidth}px`
    pill.style.transform = `translateX(${activeButton.offsetLeft - 3}px)`
    pill.style.opacity = '1'
  }

  if (!animate) {
    const prevTransition = pill.style.transition
    pill.style.transition = 'none'
    applyPosition()
    void pill.offsetWidth
    pill.style.transition = prevTransition
  } else {
    applyPosition()
  }
}

onMounted(() => {
  moveIndicator(false)
})

useResizeObserver(listRef, () => {
  moveIndicator(false)
})

watch(
  () => modelValue.value,
  async () => {
    await nextTick()
    moveIndicator(true)
  },
)

watch(
  () => props.options,
  async () => {
    await nextTick()
    moveIndicator(false)
  },
  { deep: true },
)

function selectOption(option: SegmentOption<T>) {
  if (option.disabled) return
  modelValue.value = option.value
}

function moveFocus(step: number) {
  const total = props.options.length
  if (total === 0) return

  let index = activeIndex.value
  for (let i = 0; i < total; i += 1) {
    index = (index + step + total) % total
    const candidate = props.options[index]
    if (candidate && !candidate.disabled) {
      modelValue.value = candidate.value
      tabRefs.value[index]?.focus()
      return
    }
  }
}

function focusEdge(fromEnd: boolean) {
  const indices = props.options.map((_, idx) => idx)
  if (fromEnd) indices.reverse()
  for (const idx of indices) {
    const candidate = props.options[idx]
    if (candidate && !candidate.disabled) {
      modelValue.value = candidate.value
      tabRefs.value[idx]?.focus()
      return
    }
  }
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'ArrowRight':
      event.preventDefault()
      moveFocus(1)
      break
    case 'ArrowLeft':
      event.preventDefault()
      moveFocus(-1)
      break
    case 'Home':
      event.preventDefault()
      focusEdge(false)
      break
    case 'End':
      event.preventDefault()
      focusEdge(true)
      break
  }
}

function setTabRef(el: unknown, index: number) {
  if (el instanceof HTMLButtonElement) {
    tabRefs.value[index] = el
  }
}
</script>

<template>
  <div
    ref="listRef"
    role="tablist"
    :aria-label="ariaLabel"
    class="relative items-center gap-0.5 rounded-[9px] bg-[#E5E5EA]/90 p-[3px] ring-1 ring-black/[0.06] ring-inset"
    :class="fullWidth ? 'flex w-full' : 'inline-flex max-w-full overflow-x-auto'"
  >
    <span
      ref="pillRef"
      aria-hidden="true"
      class="yuzu-tabs-pill bg-surface shadow-segment pointer-events-none absolute top-[3px] bottom-[3px] left-[3px] rounded-[7px] opacity-0"
    />

    <button
      v-for="(option, index) in options"
      :key="String(option.value)"
      :ref="(el) => setTabRef(el, index)"
      type="button"
      role="tab"
      :aria-selected="modelValue === option.value"
      :tabindex="modelValue === option.value ? 0 : -1"
      :disabled="option.disabled"
      class="yuzu-tab focus-visible:outline-accent relative z-10 inline-flex min-h-9 items-center justify-center gap-1.5 rounded-[7px] whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-1"
      :class="[
        fullWidth ? 'flex-1' : '',
        size === 'sm' ? 'px-2.5 py-1 text-[12px]' : 'px-3.5 py-1.5 text-[13px]',
        modelValue === option.value
          ? 'text-text-primary font-semibold'
          : 'text-text-secondary hover:text-text-primary font-medium',
        option.disabled ? 'cursor-not-allowed opacity-45' : 'cursor-pointer',
      ]"
      @click="selectOption(option)"
      @keydown="onKeydown"
    >
      <span>{{ option.label }}</span>
      <span
        v-if="option.badge !== undefined"
        class="rounded-full px-1.5 py-0.5 text-[11px] leading-none tabular-nums"
        :class="
          modelValue === option.value
            ? 'bg-accent-subtle text-accent'
            : 'bg-border/70 text-text-secondary'
        "
      >
        {{ option.badge }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.yuzu-tabs-pill {
  transition:
    transform var(--tabs-dur) var(--tabs-ease),
    width var(--tabs-dur) var(--tabs-ease);
  will-change: transform, width;
}

.yuzu-tab {
  transition: color var(--tabs-dur) var(--tabs-ease);
}

@media (prefers-reduced-motion: reduce) {
  .yuzu-tabs-pill,
  .yuzu-tab {
    transition: none !important;
  }
}
</style>
