<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive } from 'vue'
import { BrandMark, Stage, brandMarks, type BrandName } from '../../kit'
import './brands.css'

const names = Object.keys(brandMarks) as BrandName[]
const groups = ['Payments', 'Banks', 'Apps', 'Crypto'] as const
const themes = ['light', 'dark'] as const

const widths = reactive<Record<'light' | 'dark', number>>({ light: 0, dark: 0 })
const frameRefs = new Map<'light' | 'dark', HTMLDivElement>()

function setFrameRef(theme: 'light' | 'dark', el: any) {
  if (el instanceof HTMLDivElement) frameRefs.set(theme, el)
  else frameRefs.delete(theme)
}

const observers: ResizeObserver[] = []
onMounted(() => {
  for (const theme of themes) {
    const node = frameRefs.get(theme)
    if (!node) continue
    const measure = () => {
      widths[theme] = node.clientWidth
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    observers.push(observer)
  }
})
onBeforeUnmount(() => {
  observers.forEach(o => o.disconnect())
})

function sheetLayout(width: number) {
  const columns = width >= 600 ? 6 : 3
  const padding = width >= 600 ? 24 : 16
  const gridHeight = groups.reduce((total, group) => {
    const rows = Math.ceil(names.filter(name => brandMarks[name].category === group).length / columns)
    return total + rows * 82 + (rows - 1) * 20
  }, 0)
  const height = padding * 2 + (groups.length - 1) * 28 + groups.length * 36 + gridHeight
  return { columns, padding, height }
}
</script>

<template>
  <div class="bm-gallery">
    <section v-for="theme in themes" :key="theme" class="bm-sheet">
      <h2>{{ theme === 'light' ? 'Light' : 'Dark' }}</h2>
      <div :ref="(el) => setFrameRef(theme, el)" class="bm-frame">
        <Stage
          v-if="widths[theme] > 0"
          specimen
          :width="widths[theme]"
          :height="sheetLayout(widths[theme]).height"
          :theme="theme"
          greys="cool"
          class="bm-stage"
        >
          <div class="bm-content" :style="{ padding: `${sheetLayout(widths[theme]).padding}px` }">
            <section v-for="group in groups" :key="group" class="bm-group">
              <h3>{{ group }}</h3>
              <div class="bm-grid" :style="{ gridTemplateColumns: `repeat(${sheetLayout(widths[theme]).columns}, minmax(0, 1fr))` }">
                <div
                  v-for="brand in names.filter(name => brandMarks[name].category === group)"
                  :key="brand"
                  class="bm-item"
                >
                  <BrandMark :brand="brand" :size="40" />
                  <span>{{ brandMarks[brand].name }}</span>
                </div>
              </div>
            </section>
          </div>
        </Stage>
      </div>
    </section>
  </div>
</template>
