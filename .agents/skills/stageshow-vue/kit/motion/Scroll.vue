<script setup lang="ts">
import { onMounted, onUpdated, ref } from 'vue'
import { thumb } from '../measure'
import './Scroll.css'

export interface ScrollProps {
  name: string
  bar?: 'overlay' | 'always' | 'none'
  class?: any
  style?: any
}

const props = withDefaults(defineProps<ScrollProps>(), {
  bar: 'overlay',
})

const refEl = ref<HTMLDivElement | null>(null)

function updateThumb() {
  if (refEl.value) thumb(refEl.value)
}

onMounted(() => {
  updateThumb()
})

onUpdated(() => {
  updateThumb()
})
</script>

<template>
  <div
    class="ss-scroller"
    :class="props.class"
    :data-bar="props.bar"
    :style="props.style"
    v-bind="$attrs"
  >
    <div ref="refEl" class="ss-scroll" :data-target="props.name">
      <slot />
    </div>
    <span v-if="props.bar !== 'none'" class="ss-scroller__thumb" />
  </div>
</template>
