<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type CSSProperties } from 'vue'
import { useReducedMotion } from '../reduced-motion'
import type { Rect } from '../measure'
import { css, type Bezier, type EaseName } from '../ease'
import './Camera.css'

export interface CameraProps {
  focus: Rect | null
  pad?: number
  max?: number
  duration?: number
  feather?: number
  ease?: EaseName | Bezier
  className?: string
  class?: any
}

const props = withDefaults(defineProps<CameraProps>(), {
  pad: 32,
  max: 2,
  duration: 1100,
  feather: 28,
  ease: 'camera',
})

const refEl = ref<HTMLDivElement | null>(null)
const size = ref({ w: 0, h: 0 })
const reduced = useReducedMotion()

let ro: ResizeObserver | null = null

onMounted(() => {
  const p = refEl.value?.parentElement?.parentElement
  if (!p) return
  const read = () => {
    const w = p.offsetWidth
    const h = p.offsetHeight
    if (size.value.w !== w || size.value.h !== h) {
      size.value = { w, h }
    }
  }
  read()
  ro = new ResizeObserver(read)
  ro.observe(p)
})

onUnmounted(() => {
  ro?.disconnect()
})

const transform = computed(() => {
  if (props.focus && size.value.w) {
    const s = Math.max(
      1,
      Math.min(
        props.max,
        size.value.w / (props.focus.width + props.pad * 2),
        size.value.h / (props.focus.height + props.pad * 2),
      ),
    )
    const tx = Math.min(
      0,
      Math.max(size.value.w - size.value.w * s, size.value.w / 2 - (props.focus.x + props.focus.width / 2) * s),
    )
    const ty = Math.min(
      0,
      Math.max(size.value.h - size.value.h * s, size.value.h / 2 - (props.focus.y + props.focus.height / 2) * s),
    )
    return `translate(${tx}px, ${ty}px) scale(${s})`
  }
  return 'none'
})

const easeStr = computed(() => `${reduced.value ? 0 : props.duration}ms ${css(props.ease)}`)
</script>

<template>
  <div
    class="ss-camera-view"
    :data-zoomed="transform === 'none' ? undefined : true"
    :data-focus="transform === 'none' || !props.focus ? undefined : `${props.focus.x},${props.focus.y},${props.focus.width},${props.focus.height}`"
    :data-feather="props.feather"
    :style="{
      ['--ss-feather' as any]: `${transform === 'none' ? 0 : props.feather}px`,
      transition: `--ss-feather ${easeStr}`,
    }"
  >
    <div
      ref="refEl"
      :class="['ss-camera', props.className, props.class]"
      :style="{ transform, transition: `transform ${easeStr}` }"
    >
      <slot />
    </div>
  </div>
</template>
