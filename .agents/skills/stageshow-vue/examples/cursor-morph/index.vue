<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Segmented, Stage, type Act } from '../../kit'
import CursorMorph, { type MorphStyle } from './cursor-morph.vue'
import './cursor-morph.css'

// The cursor styles, picked by the cursor itself: four options, and each
// click turns the cursor into the one it chose. Round the four and back to
// the default, so the loop ends where it began. Here the cursor is one
// outline that morphs from style to style (cursor-morph.vue).

const STYLES: MorphStyle[] = ['real', 'large', 'circle', 'arrow']
const LABELS = ['Real', 'Large', 'Circle', 'Arrow']
const ORDER = [1, 2, 3, 0]
const REST = { x: 150, y: 150 }

type S = { value: number }

async function script(a: Act<S>) {
  await a.wait(600)
  for (const k of ORDER) {
    await a.click({ at: `opt-${k}`, x: 0.5, y: 0.62 })
    await a.set({ value: k })
    await a.wait(1000)
  }
  await a.move(REST)
  await a.wait(600)
}

const frame = ref<HTMLDivElement | null>(null)
const at = ref<HTMLElement | null>(null)
onMounted(() => {
  at.value = frame.value
})
</script>

<template>
  <Stage
    :width="550"
    :height="200"
    :compact="{ below: 540, width: 358, height: 200 }"
    :initial="{ value: 0 }"
    :script="script"
    :cursor="{ at: REST, style: 'real' }"
    class="cm-stage"
    v-slot="{ state: s }"
  >
    <div ref="frame" class="cm-frame">
      <Segmented class="cm-seg" :items="LABELS" :value="s.value" :targets="LABELS.map((_, k) => `opt-${k}`)" />
      <CursorMorph :at="at" :style="STYLES[s.value]" />
    </div>
  </Stage>
</template>
