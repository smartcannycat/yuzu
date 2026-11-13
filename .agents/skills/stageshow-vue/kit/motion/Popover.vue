<script lang="ts">
/** CSS transform-origin keywords: a side, or a vertical and horizontal pair. */
export type PopoverOrigin = 'top' | 'bottom' | 'left' | 'right' | 'center' | `${'top' | 'bottom' | 'center'} ${'left' | 'right' | 'center'}` | `${'left' | 'right'} center`
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import './Popover.css'

export interface PopoverProps {
  show: boolean
  origin?: PopoverOrigin
  className?: string
  class?: any
  style?: any
}

const props = withDefaults(defineProps<PopoverProps>(), {
  origin: 'top left',
})

const rootEl = ref<HTMLDivElement | null>(null)
const released = ref(false)
const held = ref<{ style?: any; origin: PopoverOrigin; html?: string } | null>(null)

let timer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.show,
  (show, wasShow) => {
    if (show) {
      if (timer) clearTimeout(timer)
      released.value = false
      held.value = { style: props.style, origin: props.origin }
    } else {
      if (wasShow && rootEl.value) {
        held.value = {
          style: held.value?.style ?? props.style,
          origin: held.value?.origin ?? props.origin,
          html: rootEl.value.innerHTML,
        }
      }
      timer = setTimeout(() => {
        released.value = true
      }, 320)
    }
  },
  { immediate: true, flush: 'sync' },
)

watch(() => [props.style, props.origin], () => {
  if (props.show) {
    held.value = { style: props.style, origin: props.origin }
  }
})

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

const currentOrigin = computed(() => {
  if (props.show || released.value || !held.value) {
    return props.origin
  }
  return held.value.origin
})

const currentStyle = computed(() => {
  if (props.show || released.value || !held.value) {
    return props.style
  }
  return held.value.style
})

const showFrozenHtml = computed(() => !props.show && !released.value && held.value?.html !== undefined)
</script>

<template>
  <div
    ref="rootEl"
    :class="['ss-popover', props.className, props.class]"
    :data-show="props.show || undefined"
    :data-instant="(!props.show && released) || undefined"
    :style="[
      { '--ss-popover-origin': currentOrigin },
      currentStyle,
    ]"
    v-bind="$attrs"
  >
    <div v-if="showFrozenHtml" style="display: contents" v-html="held!.html" />
    <slot v-else />
  </div>
</template>
