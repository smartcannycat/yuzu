<script setup lang="ts">
import { Bar, Facepile, Stage, Window, type Act, type Rect } from '../../kit'
import './presence.css'

// Presence: two teammates working in the same doc. Beats: Maya's cursor
// comes to a sentence and selects it, her color sweeping across it under
// her name; Jon's cursor comes to the next line and types two words with a
// caret in his color; both rest. Loops; the reset fades their edits out
// while the cursors are off at the margins.
//
// What makes presence read as people, not decoration:
// - Each person is one color everywhere: their face in the pile, their
//   cursor, their name flag, their selection, their caret. Two people, two
//   colors, neither of them the doc's accent.
// - The name rides the cursor, just below and right of its tip, so the eye
//   reads who as well as where. A bare colored arrow is just a second
//   pointer.
// - They move like hands: an ease in and out over most of a second, never
//   linear, never in step with each other.
// - Their work is in the document's own marks: a selection is a text
//   highlight, typing is words arriving at a caret. No bubbles, no badges.
// - There is no own-cursor: the viewer is watching the others.
//
// Real strings: the doc's title, the two sentences in play, the typed words,
// the two names. The rest is placeholder lines at a paragraph's measure.

type Spot = 'rest' | 'start' | 'end' | 'ins' | 'away'
type S = { maya: Spot; jon: Spot; sel: number; jonText: string; caret: boolean }

const initial: S = { maya: 'rest', jon: 'rest', sel: 0, jonText: '', caret: false }
const PEOPLE = { maya: '#d1478a', jon: '#2f9e8f' }

async function script(a: Act<S>) {
  await a.wait(700)
  a.mark('maya')
  a.put({ maya: 'start' })
  await a.wait(1000)
  a.put({ maya: 'end', sel: 1 })
  await a.wait(500)
  a.mark('jon')
  a.put({ jon: 'ins' })
  // His caret appears when he gets there, as his click places it
  await a.wait(1100)
  a.put({ caret: true })
  await a.wait(250)
  await a.type('jonText', ' and EU', { interval: 110 })
  await a.wait(2400)
  a.mark('reset')
  a.put({ maya: 'away', jon: 'away', caret: false })
  await a.wait(700)
  a.put({ sel: 0, jonText: '' })
  await a.wait(700)
  a.put({ maya: 'rest', jon: 'rest' })
  await a.wait(900)
}

function spot(who: 'maya' | 'jon', at: Spot, sel: Rect, ins: Rect, doc: Rect): { x: number; y: number } {
  // A name flag never leaves the doc: about 60px from its right edge at most
  const right = doc.x + doc.width - 64
  if (!sel.width) return { x: -100, y: -100 }
  if (who === 'maya') {
    if (at === 'start') return { x: sel.x, y: sel.y + sel.height * 0.6 }
    if (at === 'end') return { x: sel.x + sel.width, y: sel.y + sel.height * 0.6 }
    if (at === 'away') return { x: sel.x - 60, y: sel.y - 70 }
    return { x: sel.x + 40, y: sel.y - 50 }
  }
  if (at === 'ins') return { x: Math.min(right, ins.x + 2), y: ins.y + ins.height * 0.75 }
  if (at === 'away') return { x: Math.min(right, ins.x + 120), y: ins.y + 100 }
  return { x: Math.min(right, ins.x + 70), y: ins.y + 74 }
}
</script>

<template>
  <Stage
    :width="660"
    :height="420"
    :compact="{ below: 660, width: 358, height: 420 }"
    :initial="initial"
    :poster="{ maya: 'end', jon: 'ins', sel: 1, jonText: ' and EU', caret: true }"
    :script="script"
    class="pr"
    v-slot="{ state: s, rect }"
  >
    <Window title="Docs" class="pr-win">
      <template #toolbar>
        <Facepile :names="['Maya Chen', 'Jon Park', 'Ana Ruiz']" :size="22" class="pr-pile" />
      </template>
      <div class="pr-doc" data-target="doc">
        <div class="pr-title">Launch plan</div>
        <div class="pr-lines">
          <Bar w="94%" :h="7" :r="3.5" :tone="2" />
          <Bar w="88%" :h="7" :r="3.5" :tone="2" />
          <Bar w="52%" :h="7" :r="3.5" :tone="2" />
        </div>
        <p class="pr-p">
          <span class="pr-sel" data-target="sel" :data-on="s.sel || undefined" :style="{ '--who': PEOPLE.maya }">
            Pricing goes live on Thursday.
          </span>
          {{ ' ' }}Checkout opens in the US<!-- Where Jon clicked: his words arrive to the right of it --><span class="pr-anchor" data-target="ins" /><span class="pr-typed" :style="{ '--who': PEOPLE.jon }">{{ s.jonText }}<span class="pr-caret" :data-on="s.caret || undefined" :key="s.jonText" /></span>.
        </p>
        <div class="pr-lines">
          <Bar w="90%" :h="7" :r="3.5" :tone="2" />
          <Bar w="96%" :h="7" :r="3.5" :tone="2" />
          <Bar w="70%" :h="7" :r="3.5" :tone="2" />
          <Bar w="84%" :h="7" :r="3.5" :tone="2" />
        </div>
      </div>
    </Window>

    <span
      class="pr-peer"
      :style="{
        transform: `translate(${spot('maya', s.maya, rect('sel'), rect('ins'), rect('doc')).x}px, ${spot('maya', s.maya, rect('sel'), rect('ins'), rect('doc')).y}px)`,
        '--who': PEOPLE.maya,
      }"
    >
      <svg width="16" height="18" viewBox="0 0 16 18" aria-hidden="true">
        <path
          d="M1.5 1.5v13.2l3.6-3.3 2.4 5.4 2.4-1-2.4-5.3h5.1Z"
          fill="var(--who)"
          stroke="#fff"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
      </svg>
      <span class="pr-flag">Maya</span>
    </span>

    <span
      class="pr-peer"
      data-slow
      :style="{
        transform: `translate(${spot('jon', s.jon, rect('sel'), rect('ins'), rect('doc')).x}px, ${spot('jon', s.jon, rect('sel'), rect('ins'), rect('doc')).y}px)`,
        '--who': PEOPLE.jon,
      }"
    >
      <svg width="16" height="18" viewBox="0 0 16 18" aria-hidden="true">
        <path
          d="M1.5 1.5v13.2l3.6-3.3 2.4 5.4 2.4-1-2.4-5.3h5.1Z"
          fill="var(--who)"
          stroke="#fff"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
      </svg>
      <span class="pr-flag">Jon</span>
    </span>
  </Stage>
</template>
