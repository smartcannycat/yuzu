<script setup lang="ts">
import { computed, ref } from 'vue'
import { Collapse, Fly, Roll, Stage, type Act, type Rect } from '../kit'
import { MacPointer } from '../kit/cursors'
import './contrasts.css'
import RelationshipComparison, { relationshipLessons } from './relationships.vue'
import ContinuityComparison, { continuityLessons } from './continuity.vue'
import TextComparison, { textLessons } from './text-settle.vue'
import CompositionComparison, { compositionLessons } from './composition.vue'
import EdgeComparison, { edgeLessons } from './edges.vue'
import SceneComparison, { sceneLessons } from './scenes.vue'
import StyleComparison, { styleLessons } from './style.vue'
import DetailComparison, { detailLessons } from './details.vue'
import { ChoreographyComparison, choreographyLessons } from '../examples/choreography/index.vue'

type State = { done: boolean; pressed: boolean; phase: 'start' | 'change' | 'followup'; count: 0 | 1 | 2 | 3 }
type Kind = 'label' | 'press' | 'space' | 'identity' | 'exit' | 'interrupt' | 'handoff' | 'reset'
const initial: State = { done: false, pressed: false, phase: 'start', count: 0 }
const poster: State = { ...initial, done: true, phase: 'followup' }

// One Stage owns both halves: the input, result and hold happen on the same
// frame. These stationary pointers show the same comparison input twice;
// an ordinary product demo uses Stage's cursor and a.click instead.
async function script(a: Act<State>) {
  await a.wait(1100)
  for (const done of [true, false]) {
    await a.set({ pressed: true })
    await a.wait(180)
    await a.set({ pressed: false, done })
    await a.wait(1800)
  }
}

async function exitScript(a: Act<State>) {
  await a.wait(1100)
  await a.set({ pressed: true })
  await a.wait(180)
  await a.set({ pressed: false, phase: 'change' })
  await a.wait(400)
  await a.set({ phase: 'followup' })
}

async function interruptScript(a: Act<State>) {
  await a.wait(1100)
  await a.set({ phase: 'change' }) // Month
  await a.wait(200) // A second choice before the 600ms move finishes
  await a.set({ phase: 'followup' }) // Week
}

async function handoffScript(a: Act<State>) {
  await a.wait(1100)
  await a.set({ phase: 'change' })
  await a.wait(650) // The 600ms flyer rests before the destination takes over
  await a.set({ phase: 'followup' })
}

async function resetScript(a: Act<State>) {
  await a.wait(900)
  for (const count of [1, 2, 3] as const) {
    await a.set({ count })
    await a.wait(500)
  }
  await a.wait(1000)
  await a.set({ pressed: true })
  await a.wait(180)
  await a.set({ pressed: false, phase: 'change' })
  await a.wait(250)
  await a.set({ count: 0, phase: 'followup' })
}

const scripts: Partial<Record<Kind, (a: Act<State>) => Promise<void>>> = {
  exit: exitScript,
  interrupt: interruptScript,
  handoff: handoffScript,
  reset: resetScript,
}

const cases: { kind: Kind; title: string; note: string; bad: string; good: string }[] = [
  { kind: 'label', title: 'Labels that cut', note: 'Watch the button’s words change in both directions. The endpoints match; the handoff is different.', bad: 'Changes instantly', good: 'Old label exits, new label enters' },
  { kind: 'press', title: 'A press with no response', note: 'Watch the button while the pointer presses, before “Saved” appears. Both receive the same input.', bad: 'No response to the press', good: 'Responds before the result' },
  { kind: 'space', title: 'A new row that jolts its neighbors', note: 'Follow the delivery line below the note as it opens and closes. Both make exactly the same room.', bad: 'New row makes the next line jump', good: 'New row carries the next line with it' },
  { kind: 'identity', title: 'An icon that loses its identity', note: 'Watch the plus become a close icon and return. The strokes and endpoints are identical in both panels.', bad: 'Icon is replaced', good: 'Same strokes rotate into the next shape' },
  { kind: 'exit', title: 'A message that skips its exit', note: 'Watch “Link copied” when the close control is pressed. Both dismiss it; only one lets the exit finish.', bad: 'Removed on the first frame', good: 'Fades out before it is removed' },
  { kind: 'interrupt', title: 'A second choice restarts the motion', note: 'Month is selected, then Week before the highlight arrives. Follow where the highlight starts its second move.', bad: 'Restarts from Day', good: 'Continues from its current position' },
  { kind: 'handoff', title: 'An object jumps when it lands', note: 'Watch the avatar at the end of its flight. Measuring its padded slot puts the landing four pixels away from the avatar.', bad: 'Lands on the slot, then jumps inward', good: 'Lands on the measured avatar' },
  { kind: 'reset', title: 'A loop erases the work', note: 'Three files accumulate, then clear at the same moment. Look for the action that explains why they disappear.', bad: 'Files clear without an action', good: 'A Clear press explains the reset' },
]

const handoffTarget = (good: boolean, part: 'source' | 'destination' | 'slot') =>
  `handoff-${good ? 'good' : 'bad'}-${part}`
const FILES = ['Draft.pdf', 'Notes.txt', 'Plan.md']
const TAB_LABELS = ['Day', 'Week', 'Month']

function interruptSelected(phase: State['phase']) {
  return phase === 'start' ? 0 : phase === 'change' ? 2 : 1
}

function handoffTo(good: boolean, rect: (target: string) => Rect): Rect {
  const destination = rect(handoffTarget(good, 'destination'))
  const slot = rect(handoffTarget(good, 'slot'))
  return good ? destination : { ...destination, x: slot.x, y: slot.y }
}

const motionLessons = [
  ...cases.map((lesson) => ({ id: lesson.kind, title: lesson.title })),
  ...relationshipLessons,
  ...continuityLessons,
  ...textLessons,
  ...edgeLessons,
  ...choreographyLessons,
]
const lessons = [...motionLessons, ...compositionLessons, ...sceneLessons, ...styleLessons, ...detailLessons]

const initialLesson = (() => {
  const value = typeof window === 'undefined' ? null : new URLSearchParams(location.search).get('lesson')
  return lessons.some((lesson) => lesson.id === value) ? value! : 'label'
})()

const selected = ref<string>(initialLesson)
const revision = ref(0)

function choose(value: string) {
  selected.value = value
  revision.value = 0
  const url = new URL(location.href)
  url.searchParams.set('lesson', value)
  history.replaceState(null, '', url)
  if (parent !== window) parent.postMessage({ type: 'stageshow:status', lesson: value }, location.origin)
}

const original = computed(() => cases.find((lesson) => lesson.kind === selected.value))
const originalHeight = computed(() =>
  original.value?.kind === 'space' ? 244 : original.value?.kind === 'reset' ? 232 : 150,
)
const originalSequence = computed(() => (original.value ? scripts[original.value.kind] : undefined))
</script>

<template>
  <div class="tc-lessons">
    <div class="tc-picker">
      <label for="comparison-principle">Principle</label>
      <select
        id="comparison-principle"
        :value="selected"
        @change="choose(($event.target as HTMLSelectElement).value)"
      >
        <optgroup label="Motion">
          <option v-for="lesson in motionLessons" :key="lesson.id" :value="lesson.id">
            {{ lesson.title }}
          </option>
        </optgroup>
        <optgroup label="UI details">
          <option v-for="lesson in compositionLessons" :key="lesson.id" :value="lesson.id">
            {{ lesson.title }}
          </option>
        </optgroup>
        <optgroup label="Whole compositions">
          <option v-for="lesson in sceneLessons" :key="lesson.id" :value="lesson.id">
            {{ lesson.title }}
          </option>
        </optgroup>
        <optgroup label="Style">
          <option v-for="lesson in styleLessons" :key="lesson.id" :value="lesson.id">
            {{ lesson.title }}
          </option>
        </optgroup>
        <optgroup label="Details">
          <option v-for="lesson in detailLessons" :key="lesson.id" :value="lesson.id">
            {{ lesson.title }}
          </option>
        </optgroup>
      </select>
    </div>

    <!-- Original motion cases -->
    <section v-if="original" :key="selected">
      <header>
        <div>
          <h2>{{ original.title }}</h2>
          <p>{{ original.note }}</p>
        </div>
        <button
          class="tc-replay"
          type="button"
          :aria-label="`Replay ${original.title.toLowerCase()}`"
          @click="revision++"
        >
          Replay pair
        </button>
      </header>
      <Stage
        :key="`${selected}-${revision}`"
        :width="704"
        :height="originalHeight"
        :compact="{ below: 704, width: 340, height: originalHeight * 2 + 16 }"
        :initial="initial"
        :poster="original.kind === 'exit' ? initial : poster"
        :script="originalSequence ?? script"
        :play="originalSequence ? 'once' : 'loop'"
        class="tc-stage"
        v-slot="{ state, rect }"
      >
        <div class="tc-pair" :data-kind="original.kind">
          <figure v-for="corrected in [false, true]" :key="String(corrected)">
            <div class="tc-visual">
              <!-- exit -->
              <div v-if="original.kind === 'exit'" class="tc-exit">
                <div
                  v-if="state.phase !== 'followup' && (corrected || state.phase !== 'change')"
                  class="tc-toast"
                  :data-leaving="state.phase === 'change' || undefined"
                >
                  <span>Link copied</span>
                  <span class="tc-dismiss" :data-pressed="state.pressed || undefined">
                    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                      <path d="m3 3 6 6M9 3 3 9" />
                    </svg>
                  </span>
                </div>
                <span
                  class="tc-pointer"
                  :data-pressed="state.pressed || undefined"
                  :data-hidden="state.phase === 'followup' || undefined"
                  aria-hidden="true"
                >
                  <component :is="MacPointer" />
                </span>
              </div>

              <!-- interrupt -->
              <div v-else-if="original.kind === 'interrupt'" class="tc-tabs">
                <span
                  :key="corrected ? 'persistent' : state.phase"
                  class="tc-tabs__highlight"
                  :data-restart="!corrected || undefined"
                  :style="{ transform: `translateX(${interruptSelected(state.phase) * 100}%)` }"
                />
                <span
                  v-for="(label, i) in TAB_LABELS"
                  :key="label"
                  class="tc-tabs__label"
                  :data-selected="i === interruptSelected(state.phase) || undefined"
                >
                  {{ label }}
                </span>
              </div>

              <!-- handoff -->
              <div v-else-if="original.kind === 'handoff'" class="tc-handoff">
                <span
                  class="tc-avatar"
                  :data-target="handoffTarget(corrected, 'source')"
                  :data-hidden="state.phase !== 'start' || undefined"
                >
                  AT
                </span>
                <div class="tc-assignee">
                  <span class="tc-avatar-slot" :data-target="handoffTarget(corrected, 'slot')">
                    <span
                      class="tc-avatar"
                      :data-target="handoffTarget(corrected, 'destination')"
                      :data-hidden="state.phase !== 'followup' || undefined"
                    >
                      AT
                    </span>
                  </span>
                  <span>Assignee</span>
                </div>
              </div>

              <!-- reset -->
              <div v-else-if="original.kind === 'reset'" class="tc-reset" :data-good="corrected || undefined">
                <div class="tc-reset__head">
                  <span>
                    <Roll>{{ `${state.count} ${state.count === 1 ? 'file' : 'files'}` }}</Roll>
                  </span>
                  <div class="tc-action">
                    <div class="tc-button" :data-pressed="(state.pressed && corrected) || undefined">Clear</div>
                    <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                      <component :is="MacPointer" />
                    </span>
                  </div>
                </div>
                <div class="tc-files" :data-clearing="state.phase === 'change' || undefined">
                  <span v-if="state.count === 0" class="tc-files__empty">No files yet</span>
                  <template v-else>
                    <span v-for="file in FILES.slice(0, state.count)" :key="file" class="tc-file">
                      <svg width="14" height="16" viewBox="0 0 14 16" aria-hidden="true">
                        <path d="M3 1.5h5l3 3v10H3zM8 1.5v3h3" />
                      </svg>
                      {{ file }}
                    </span>
                  </template>
                </div>
              </div>

              <!-- label -->
              <div v-else-if="original.kind === 'label'" class="tc-card tc-label-card">
                <div class="tc-action">
                  <div class="tc-button" :data-pressed="state.pressed || undefined">
                    <span class="tc-label">
                      <Roll v-if="corrected" variant="fade">
                        {{ state.done ? 'Back to editor' : 'Open preview' }}
                      </Roll>
                      <template v-else>{{ state.done ? 'Back to editor' : 'Open preview' }}</template>
                    </span>
                  </div>
                  <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                    <component :is="MacPointer" />
                  </span>
                </div>
              </div>

              <!-- press -->
              <div v-else-if="original.kind === 'press'" class="tc-card tc-press-card">
                <div class="tc-action">
                  <div class="tc-button" :data-pressed="(state.pressed && corrected) || undefined">
                    <span class="tc-label">
                      <Roll variant="fade">{{ state.done ? 'Saved' : 'Save changes' }}</Roll>
                    </span>
                  </div>
                  <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                    <component :is="MacPointer" />
                  </span>
                </div>
              </div>

              <!-- space -->
              <div
                v-else-if="original.kind === 'space'"
                class="tc-card tc-space-card"
                :data-good="corrected || undefined"
              >
                <div class="tc-delivery-heading">
                  <h3>Delivery</h3>
                  <div class="tc-action">
                    <div class="tc-button" :data-pressed="state.pressed || undefined">
                      <Roll variant="fade">{{ state.done ? 'Hide note' : 'Add note' }}</Roll>
                    </div>
                    <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                      <component :is="MacPointer" />
                    </span>
                  </div>
                </div>
                <Collapse class="tc-note" :open="state.done" reveal="drop">
                  <p>Leave at reception.</p>
                </Collapse>
                <div class="tc-delivery-line">
                  <span>Standard shipping</span>
                  <span>Free</span>
                </div>
              </div>

              <!-- identity -->
              <div
                v-else
                class="tc-card tc-identity-card"
                :data-good="corrected || undefined"
                :data-open="state.done || undefined"
              >
                <div class="tc-action tc-action--icon">
                  <div class="tc-button" :data-pressed="state.pressed || undefined">
                    <svg
                      :key="corrected ? 'persistent' : String(state.done)"
                      class="tc-glyph"
                      width="24"
                      height="24"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path d="M5 12H19M12 5V19" />
                    </svg>
                  </div>
                  <span class="tc-pointer" :data-pressed="state.pressed || undefined" aria-hidden="true">
                    <component :is="MacPointer" />
                  </span>
                </div>
              </div>
            </div>
            <figcaption>{{ corrected ? original.good : original.bad }}</figcaption>
          </figure>
        </div>

        <template v-if="original.kind === 'handoff' && state.phase !== 'followup'">
          <Fly
            v-for="good in [false, true]"
            :key="String(good)"
            :from="rect(handoffTarget(good, 'source'))"
            :to="handoffTo(good, rect)"
            :go="state.phase === 'change'"
            :duration="600"
          >
            <span class="tc-avatar">AT</span>
          </Fly>
        </template>
      </Stage>
    </section>

    <ChoreographyComparison v-else-if="choreographyLessons.some((lesson) => lesson.id === selected)" />
    <RelationshipComparison
      v-else-if="relationshipLessons.some((lesson) => lesson.id === selected)"
      :key="selected"
      :lesson-id="selected"
    />
    <TextComparison v-else-if="selected === 'text-settle'" />
    <CompositionComparison
      v-else-if="compositionLessons.some((lesson) => lesson.id === selected)"
      :key="selected"
      :lesson-id="selected"
    />
    <SceneComparison
      v-else-if="sceneLessons.some((lesson) => lesson.id === selected)"
      :key="selected"
      :lesson-id="selected"
    />
    <StyleComparison
      v-else-if="styleLessons.some((lesson) => lesson.id === selected)"
      :key="selected"
      :lesson-id="selected"
    />
    <DetailComparison
      v-else-if="detailLessons.some((lesson) => lesson.id === selected)"
      :key="selected"
      :lesson-id="selected"
    />
    <EdgeComparison
      v-else-if="edgeLessons.some((lesson) => lesson.id === selected)"
      :key="selected"
      :lesson-id="selected"
    />
    <ContinuityComparison v-else :key="selected" :lesson-id="selected" />
  </div>
</template>
