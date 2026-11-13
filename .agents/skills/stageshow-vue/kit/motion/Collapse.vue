<script setup lang="ts">
import { ref, onMounted, onUpdated, onBeforeUnmount, watch, type CSSProperties } from 'vue'
import './Collapse.css'

export interface CollapseProps {
  open: boolean
  reveal?: 'clip' | 'drop'
  from?: 'above' | 'below'
  solid?: boolean
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = withDefaults(defineProps<CollapseProps>(), {
  reveal: 'clip',
  from: 'above',
  solid: false,
})

const moving = ref(false)
const tall = ref(false)
const inner = ref<HTMLDivElement | null>(null)
let timer = 0

function measure() {
  const h = inner.value?.scrollHeight ?? 0
  if (h) tall.value = h > 44
}

onMounted(() => {
  measure()
})

onUpdated(() => {
  measure()
})

watch(
  () => props.open,
  () => {
    measure()
    moving.value = true
    clearTimeout(timer)
    timer = window.setTimeout(() => {
      moving.value = false
    }, 900)
  },
  { flush: 'post' },
)

onBeforeUnmount(() => {
  clearTimeout(timer)
})

function onTransitionEnd(e: TransitionEvent) {
  if (e.target === e.currentTarget && e.propertyName === 'grid-template-rows') {
    moving.value = false
  }
}
</script>

<template>
  <div
    :class="['ss-collapse', props.className, props.class]"
    :data-open="props.open || undefined"
    :data-reveal="props.reveal"
    :data-solid="props.solid || undefined"
    :data-from="props.reveal === 'drop' ? props.from : undefined"
    :data-moving="moving || undefined"
    :data-tall="tall || undefined"
    :style="props.style"
    @transitionend="onTransitionEnd"
    v-bind="$attrs"
  >
    <div class="ss-collapse__clip">
      <div ref="inner" class="ss-collapse__inner">
        <slot />
      </div>
    </div>
  </div>
</template>
