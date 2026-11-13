<script lang="ts">
export const textLessons = [
  {
    id: 'text-settle',
    title: 'Text shifts as the transition finishes',
    note: 'Watch the label and “Optional” as the old words finish fading. Hidden text can still move the line’s baseline.',
    bad: 'A hidden label changes the baseline',
    good: 'Travel stays separate from layout',
  },
] as const
</script>

<script setup lang="ts">
import { ref } from 'vue'
import { Stage, States, type Act } from '../kit'
import './text-settle.css'

type State = { added: boolean }
const labels = { empty: 'Add a note', added: 'Note added' }
const labelEntries = Object.entries(labels)

async function sequence(a: Act<State>) {
  await a.wait(1300)
  await a.set({ added: true })
  await a.wait(2000)
  await a.set({ added: false })
  await a.wait(1400)
}

const revision = ref(0)
const lesson = textLessons[0]
</script>

<template>
  <section class="ts-lesson">
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
      :height="150"
      :compact="{ below: 704, width: 340, height: 316 }"
      :initial="{ added: false }"
      :poster="{ added: true }"
      :script="sequence"
      play="once"
      class="tc-stage"
      v-slot="{ state }"
    >
      <div class="tc-pair">
        <figure v-for="good in [false, true]" :key="String(good)">
          <div class="tc-visual">
            <div class="ts-line" :data-good="good || undefined">
              <span class="ts-label">
                <States v-if="good" :value="state.added ? 'added' : 'empty'" :states="labels" align="start" />
                <span v-else class="ts-unstable">
                  <span
                    v-for="[key, text] in labelEntries"
                    :key="key"
                    class="ts-unstable__item"
                    :data-on="(state.added ? 'added' : 'empty') === key || undefined"
                    :aria-hidden="(state.added ? 'added' : 'empty') !== key || undefined"
                  >
                    {{ text }}
                  </span>
                </span>
              </span>
              <span class="ts-secondary">Optional</span>
            </div>
          </div>
          <figcaption>{{ good ? lesson.good : lesson.bad }}</figcaption>
        </figure>
      </div>
    </Stage>
  </section>
</template>
