<script setup lang="ts">
import { computed } from 'vue'
import './Stream.css'

export interface StreamProps {
  text: string
  count: number
  mark?: (word: string, i: number) => boolean
  class?: any
  style?: any
}

const props = defineProps<StreamProps>()

const words = computed(() => (props.text ? props.text.split(' ') : []))
const marked = computed(() => words.value.map((w, i) => !!props.mark?.(w, i)))
</script>

<template>
  <span
    class="ss-stream"
    :class="props.class"
    :style="props.style"
    v-bind="$attrs"
  >
    <span v-for="(w, i) in words" :key="i">
      <span
        class="ss-stream__w"
        :data-on="i < props.count || undefined"
        :data-mark="marked[i] || undefined"
        :data-join="(marked[i] && marked[i + 1]) || undefined"
        :data-joined="(marked[i] && marked[i - 1]) || undefined"
      >
        {{ w }}{{ marked[i] && marked[i + 1] ? ' ' : '' }}
      </span>
      {{ !(marked[i] && marked[i + 1]) && i < words.length - 1 ? ' ' : '' }}
    </span>
  </span>
</template>
