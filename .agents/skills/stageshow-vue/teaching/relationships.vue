<script lang="ts">
export const relationshipLessons = [
  { id: 'horizontal-insert', title: 'An insertion moves what follows', note: 'Watch “Design review” as the check appears and disappears. The check needs room, and the existing label should travel with that room.', bad: 'The label jumps sideways', good: 'The label follows the opening space' },
  { id: 'list-reflow', title: 'A new row carries the list', note: 'Follow Maya and Jon when Ana is added and removed. The new row arrives whole while the existing rows make room.', bad: 'Existing rows jump down and back', good: 'The list opens and closes around the row' },
  { id: 'adjacent-action', title: 'A control carries the next action', note: 'Watch Settings while the first button changes width. Its position belongs to the same motion as the button’s edge.', bad: 'Settings jumps to the new edge', good: 'Settings travels with the changing width' },
  { id: 'surface-resize', title: 'A popup resizes with its content', note: 'Watch the popup grow, return, then reverse before it finishes. The outline and content should belong to one continuous change.', bad: 'The outline jumps ahead of the content', good: 'The surface follows the same live motion' },
] as const
</script>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Collapse, Roll, Stage, type Act } from '../kit'
import { MacPointer } from '../kit/cursors'
import './contrasts.css'
import './relationships.css'

const props = defineProps<{
  lessonId: string
}>()

type State = { active: boolean; pressed: boolean }
const initial: State = { active: false, pressed: false }
const poster: State = { active: true, pressed: false }

async function change(a: Act<State>, active: boolean, press = 100) {
  await a.set({ pressed: true })
  await a.wait(press)
  await a.set({ pressed: false, active })
}

async function script(a: Act<State>) {
  await a.wait(1000)
  a.mark('insert')
  await change(a, true)
  await a.wait(1500)
  a.mark('remove')
  await change(a, false)
  await a.wait(1300)
}

async function surfaceScript(a: Act<State>) {
  await script(a)
  a.mark('interrupt-open')
  await change(a, true)
  await a.wait(40)
  a.mark('interrupt-return')
  await change(a, false, 40)
  await a.wait(1200)
}

const revision = ref(0)
const lesson = computed(() => relationshipLessons.find((item) => item.id === props.lessonId))
const height = computed(() =>
  lesson.value?.id === 'list-reflow' ? 226 : lesson.value?.id === 'surface-resize' ? 198 : 150,
)
</script>

<template>
  <section v-if="lesson" class="tr-lesson">
    <header>
      <div>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.note }}</p>
      </div>
      <button
        type="button"
        class="tc-replay"
        :aria-label="`Replay ${lesson.title.toLowerCase()}`"
        @click="revision++"
      >
        Replay pair
      </button>
    </header>
    <Stage
      :key="`${lesson.id}-${revision}`"
      :width="704"
      :height="height"
      :compact="{ below: 704, width: 340, height: height * 2 + 16 }"
      :initial="initial"
      :poster="poster"
      :script="lesson.id === 'surface-resize' ? surfaceScript : script"
      play="once"
      class="tc-stage"
      v-slot="{ state }"
    >
      <div class="tc-pair tr-pair" :data-relationship="lesson.id">
        <figure v-for="good in [false, true]" :key="String(good)">
          <div class="tc-visual">
            <!-- horizontal-insert -->
            <div
              v-if="lesson.id === 'horizontal-insert'"
              class="tr-inline"
              :data-good="good || undefined"
              :data-active="state.active || undefined"
            >
              <div class="tr-inline__line">
                <span class="tr-inline__slot">
                  <span class="tr-inline__check">
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                      <path d="m3 7 2.5 2.5L11 4" />
                    </svg>
                  </span>
                </span>
                <span class="tr-inline__label">Design review</span>
              </div>
              <div class="tr-trigger">
                <div class="tc-button" :data-pressed="state.pressed || undefined">
                  <Roll variant="fade">{{ state.active ? 'Undo' : 'Verify' }}</Roll>
                </div>
                <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                  <component :is="MacPointer" />
                </span>
              </div>
            </div>

            <!-- list-reflow -->
            <div v-else-if="lesson.id === 'list-reflow'" class="tr-list" :data-good="good || undefined">
              <div class="tr-list__head">
                <span>Reviewers</span>
                <div class="tr-trigger">
                  <div class="tc-button" :data-pressed="state.pressed || undefined">
                    <Roll variant="fade">{{ state.active ? 'Remove Ana' : 'Add Ana' }}</Roll>
                  </div>
                  <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                    <component :is="MacPointer" />
                  </span>
                </div>
              </div>
              <div class="tr-list__rows">
                <Collapse class="tr-list__insert" :open="state.active" reveal="drop">
                  <div class="tr-person" data-added="true">
                    <span class="tr-person__avatar">A</span>
                    <span>Ana</span>
                    <span class="tr-person__role">Reviewer</span>
                  </div>
                </Collapse>
                <div class="tr-person">
                  <span class="tr-person__avatar">M</span>
                  <span>Maya</span>
                  <span class="tr-person__role">Reviewer</span>
                </div>
                <div class="tr-person">
                  <span class="tr-person__avatar">J</span>
                  <span>Jon</span>
                  <span class="tr-person__role">Reviewer</span>
                </div>
              </div>
            </div>

            <!-- adjacent-action -->
            <div v-else-if="lesson.id === 'adjacent-action'" class="tr-actions" :data-good="good || undefined">
              <div class="tr-trigger">
                <div class="tc-button" :data-pressed="state.pressed || undefined">
                  <Roll variant="fade" align="start">
                    {{ state.active ? 'Disconnect account' : 'Connect' }}
                  </Roll>
                </div>
              </div>
              <span class="tr-actions__next">Settings</span>
              <!-- The input stays where it happened while the result changes size. -->
              <div class="tr-press-anchor" aria-hidden="true">
                <div class="tc-button tr-press-measure">Connect</div>
                <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                  <component :is="MacPointer" />
                </span>
              </div>
            </div>

            <!-- surface-resize -->
            <div v-else class="tr-surface" :data-good="good || undefined" :data-active="state.active || undefined">
              <div class="tr-popup">
                <span class="tr-popup__title">Link access</span>
                <span class="tr-popup__detail">Anyone with the link can view.</span>
              </div>
              <div class="tr-trigger">
                <div class="tc-button" :data-pressed="state.pressed || undefined">
                  <Roll variant="fade">{{ state.active ? 'Less detail' : 'More detail' }}</Roll>
                </div>
                <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                  <component :is="MacPointer" />
                </span>
              </div>
            </div>
          </div>
          <figcaption>{{ good ? lesson.good : lesson.bad }}</figcaption>
        </figure>
      </div>
    </Stage>
  </section>
</template>
