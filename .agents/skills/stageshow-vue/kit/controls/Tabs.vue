<script setup lang="ts">
import { ref, onMounted, watch, nextTick, type CSSProperties } from 'vue'
import './Tabs.css'

export interface TabsProps {
  items: any[]
  value: number
  targets?: (string | undefined)[]
  className?: string
  class?: any
  style?: CSSProperties | any
}

const props = defineProps<TabsProps>()

const row = ref<HTMLDivElement | null>(null)
const bar = ref({ x: 0, w: 0 })

function measureBar() {
  if (!row.value) return
  const el = row.value.children[props.value + 1] as HTMLElement | undefined
  if (el) {
    bar.value = { x: el.offsetLeft, w: el.offsetWidth }
  }
}

onMounted(() => {
  measureBar()
})

watch(
  () => [props.value, props.items.length],
  () => {
    nextTick(() => measureBar())
  },
)
</script>

<template>
  <div ref="row" :class="['ss-tabs', props.className, props.class]" :style="props.style">
    <span
      class="ss-tabs__bar"
      :style="{ transform: `translateX(${bar.x}px) scaleX(${bar.w})` }"
    />
    <span
      v-for="(t, i) in props.items"
      :key="i"
      class="ss-tabs__tab"
      :data-on="i === props.value || undefined"
      :data-target="props.targets?.[i]"
    >
      <component :is="() => t" v-if="typeof t === 'object' && t !== null && 'render' in t" />
      <template v-else>{{ t }}</template>
    </span>
  </div>
</template>
