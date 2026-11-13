<script lang="ts">
export const edgeLessons = [
  { id: 'label-boundary', title: 'A label hits a hard edge', note: 'Watch the letter shapes at the top and bottom of the button’s label slot. The boundary should soften the moving text, while resting text stays sharp.', bad: 'Letters are sliced by the slot', good: 'Letters soften as they reach the edge' },
  { id: 'viewport-edge', title: 'Scrolling content meets the edge', note: 'Both lists start with three whole rows. After scrolling begins, the softened edges indicate content above or below; they clear when no content remains hidden there.', bad: 'Rows meet an abrupt clipping edge', good: 'Only the concealed edges are softened' },
] as const
</script>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Stage, type Act } from '../kit'
import './edges.css'

const props = defineProps<{
  lessonId: string
}>()

type State = { changed: boolean; offset: 0 | 45 | 64; moving: boolean; started: boolean }
const initial: State = { changed: false, offset: 0, moving: false, started: false }

async function labels(a: Act<State>) {
  await a.wait(1200)
  await a.set({ changed: true })
  await a.wait(2000)
  await a.set({ changed: false })
}

async function scrolling(a: Act<State>) {
  await a.wait(1200)
  await a.set({ offset: 45, moving: true, started: true })
  await a.wait(900)
  await a.set({ moving: false })
  await a.wait(800)
  await a.set({ offset: 64, moving: true })
  await a.wait(900)
  await a.set({ moving: false })
  await a.wait(1200)
  await a.set({ offset: 0, moving: true })
  await a.wait(900)
  await a.set({ moving: false })
}

const FILES = ['Brief.pdf', 'Wireframes.fig', 'Review.md', 'Prototype.fig', 'Notes.txt'] as const
const SIZES = [24, 182, 4, 96, 2] as const

const revision = ref(0)
const lesson = computed(() => edgeLessons.find((item) => item.id === props.lessonId)!)
const viewport = computed(() => lesson.value.id === 'viewport-edge')
const height = computed(() => (viewport.value ? 218 : 150))
</script>

<template>
  <section>
    <header>
      <div>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.note }}</p>
      </div>
      <button class="tc-replay" type="button" @click="revision++">Replay pair</button>
    </header>
    <Stage
      :key="revision"
      :width="704"
      :height="height"
      :compact="{ below: 704, width: 340, height: height * 2 + 16 }"
      :initial="initial"
      :poster="{ ...initial, changed: true }"
      :script="viewport ? scrolling : labels"
      play="once"
      class="tc-stage"
      v-slot="{ state }"
    >
      <div class="tc-pair ed-pair" :data-viewport="viewport || undefined">
        <figure v-for="good in [false, true]" :key="String(good)">
          <div class="tc-visual">
            <div v-if="viewport" class="ed-files" :data-good="good || undefined">
              <div class="ed-files-heading">Project files<span>5 files</span></div>
              <div
                class="ed-viewport"
                :data-top="(state.started && (state.offset > 0 || state.moving)) || undefined"
                :data-bottom="(state.started && (state.offset < 64 || state.moving) && (state.offset > 0 || state.moving)) || undefined"
              >
                <div class="ed-file-track" :style="{ transform: `translate3d(0, ${-state.offset}px, 0)` }">
                  <div v-for="(file, i) in FILES" :key="file" class="ed-file">
                    <span>{{ file }}</span>
                    <span>{{ SIZES[i] }} KB</span>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="ed-button" :data-good="good || undefined" :data-changed="state.changed || undefined">
              <span class="ed-label-window">
                <span class="ed-label-track">
                  <span>Upload file</span>
                  <span>Uploaded</span>
                </span>
              </span>
            </div>
          </div>
          <figcaption>{{ good ? lesson.good : lesson.bad }}</figcaption>
        </figure>
      </div>
    </Stage>
  </section>
</template>
