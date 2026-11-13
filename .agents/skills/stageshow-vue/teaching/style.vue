<script lang="ts">
// Style pairs: the same deploys card twice. The good side is identical in
// every pair; each bad side carries one fault agents reach for, so a
// builder can match a fault in its own still to the pair that names it.

export const styleLessons = [
  { id: 'style-purple', title: 'Take the color from the product', note: 'The same deploys card. A purple-to-pink gradient, gradient text and a tinted card say “generated” before anything is read. Use the product’s own neutrals and one accent on the thing that matters.', bad: 'Purple gradient ground, gradient title, tinted everything', good: 'Product neutrals; the accent only on the live deploy' },
  { id: 'style-tiny', title: 'Set text at reading size', note: 'The same card. Shrinking type to fit more in reads as a wireframe at launch-page size. Rows at 13 to 14px with 11 to 12px metadata, and fewer of them.', bad: '9 to 10px text that only reads zoomed in', good: '14px names, 12px metadata' },
  { id: 'style-detail', title: 'Detail only the subject', note: 'The same card. A real name, branch, hash, author, duration and badge on every row makes every row the subject. Give real words to the row the story is about; the rest can be quiet.', bad: 'Every row carries six facts and a badge', good: 'One row in full; the others name and time' },
  { id: 'style-glow', title: 'Shadows sit, they don’t glow', note: 'The same card. Colored glows around the card, the button and the status read as a neon template. A real surface casts one soft neutral shadow.', bad: 'A colored glow on the card, button and dot', good: 'One neutral shadow under the card' },
  { id: 'style-caps', title: 'Write in sentence case', note: 'The same card. Tracked capitals on the heading, labels and button shout and slow reading. Keep capitals for what the product itself capitalizes.', bad: 'Capitals on the heading, labels and button', good: 'Sentence case everywhere' },
  { id: 'style-icons', title: 'Use an icon pack, not glyphs drawn on the fly', note: 'The same card. Glyphs drawn for the demo, in colored squircles, each a different hue, filled beside outlined, read as made up. Take the product’s own set, or one pack chosen on purpose (Lucide, Phosphor, SF Symbols), one stroke, one color. Draw an icon only when no pack has it.', bad: 'Invented glyphs in rainbow tiles', good: 'One set, one stroke, status in color only' },
  { id: 'style-onion', title: 'Color icons with an opaque ink', note: 'The same card. An icon colored with a translucent ink paints darker wherever its strokes cross or join: the onion-skin look of generated UI. Use one opaque color; for a lighter icon pick a lighter opaque gray. Shown at 2x.', bad: 'Translucent ink: darker where strokes cross', good: 'One opaque color per icon' },
  { id: 'style-sparkle', title: 'Name the AI action, don’t sparkle it', note: 'The same card with an action on the failed deploy. Sparkles, wands and gradient “AI” chips are the generic shorthand for any AI feature and say nothing about this one. Use the product’s own mark if it has one; otherwise a plain label that says what happens.', bad: 'Sparkles, a wand and a gradient AI chip', good: 'A plain action that says what it does' },
] as const

type Id = (typeof styleLessons)[number]['id']
</script>

<script setup lang="ts">
import { computed, defineComponent, h, type Component, type PropType } from 'vue'
import { CircleX, GitBranch, Globe, LoaderCircle, Sparkles, WandSparkles } from 'lucide-vue-next'
import { Stage } from '../kit'
import './style.css'

const props = defineProps<{
  lessonId: string
}>()

type Deploy = { name: string; branch: string; hash: string; who: string; time: string; state: 'live' | 'building' | 'failed' }

const DEPLOYS: Deploy[] = [
  { name: 'Checkout redesign', branch: 'main', hash: '8f2c1a4', who: 'Maya Chen', time: 'Just now', state: 'live' },
  { name: 'Search speedup', branch: 'perf/search', hash: 'b41e09d', who: 'Jon Park', time: '12m ago', state: 'building' },
  { name: 'Pricing copy', branch: 'copy/pricing', hash: '3a7f6c2', who: 'Ana Ruiz', time: '1h ago', state: 'failed' },
]

const ICON: Record<Deploy['state'], Component> = { live: Globe, building: LoaderCircle, failed: CircleX }

/** Invented glyphs, the kind a builder draws when it has no set */
const MadeUp = defineComponent({
  props: {
    state: { type: String as PropType<Deploy['state']>, required: true },
  },
  setup(p) {
    return () => {
      const d = {
        live: 'M4 10.5 8 14l8-9',
        building: 'M10 3a7 7 0 1 1-6.2 3.8M3 3v4h4',
        failed: 'M10 2.5 18 17H2zM10 8v4M10 14.5v.5',
      }[p.state]
      const fill = p.state === 'failed'
      return h('span', { class: 'st-blob', 'data-state': p.state }, [
        h('svg', { width: '16', height: '16', viewBox: '0 0 20 20', 'aria-hidden': 'true' }, [
          h('path', {
            d,
            fill: fill ? 'currentColor' : 'none',
            stroke: 'currentColor',
            'stroke-width': p.state === 'building' ? 3 : 2.2,
            'stroke-linecap': 'round',
            'stroke-linejoin': 'round',
          }),
        ]),
      ])
    }
  },
})

const lesson = computed(() => styleLessons.find((item) => item.id === props.lessonId))
const height = 302

function faultFor(good: boolean, id: Id): Id | undefined {
  return good || id === 'style-sparkle' ? undefined : id
}

function aiFor(good: boolean, id: Id): 'bad' | 'good' | undefined {
  return id === 'style-sparkle' ? (good ? 'good' : 'bad') : undefined
}
</script>

<template>
  <section v-if="lesson" class="cp-lesson">
    <header>
      <div>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.note }}</p>
      </div>
    </header>
    <Stage :width="704" :height="height" :compact="{ below: 704, width: 340, height: height * 2 + 16 }" class="tc-stage">
      <div class="tc-pair st-pair" :data-style="lesson.id">
        <figure v-for="good in [false, true]" :key="String(good)">
          <div class="tc-visual" :data-good="good || undefined">
            <div class="st-card" :data-fault="faultFor(good, lesson.id)">
              <div class="st-head">
                <span class="st-title">
                  {{ faultFor(good, lesson.id) === 'style-caps' ? 'RECENT DEPLOYS' : 'Recent deploys' }}
                </span>
                <span class="st-button">
                  <MadeUp v-if="faultFor(good, lesson.id) === 'style-icons'" state="live" />
                  {{ faultFor(good, lesson.id) === 'style-caps' ? 'DEPLOY' : 'Deploy' }}
                </span>
              </div>
              <div v-if="faultFor(good, lesson.id) === 'style-caps'" class="st-eyebrow">PRODUCTION · 3 DEPLOYS</div>
              <div v-for="(d, i) in DEPLOYS" :key="d.name" class="st-row" :data-state="d.state">
                <MadeUp v-if="faultFor(good, lesson.id) === 'style-icons'" :state="d.state" />
                <span v-else class="st-icon">
                  <component :is="ICON[d.state]" :size="16" :stroke-width="1.75" />
                </span>
                <div class="st-text">
                  <span class="st-name">{{ d.name }}</span>
                  <span v-if="faultFor(good, lesson.id) === 'style-detail' || i === 0" class="st-meta">
                    <template v-if="faultFor(good, lesson.id) === 'style-detail'">
                      <GitBranch :size="11" :stroke-width="2" /> {{ d.branch }} · {{ d.hash }} · {{ d.who }} · 42s
                    </template>
                    <template v-else-if="faultFor(good, lesson.id) === 'style-caps'">
                      {{ `${d.branch.toUpperCase()} · ${d.who.toUpperCase()}` }}
                    </template>
                    <template v-else>
                      {{ `${d.branch} · ${d.who}` }}
                    </template>
                  </span>
                </div>
                <span v-if="faultFor(good, lesson.id) === 'style-detail'" class="st-badge" :data-state="d.state">
                  {{ d.state }}
                </span>
                <template v-if="aiFor(good, lesson.id) && d.state === 'failed'">
                  <span v-if="aiFor(good, lesson.id) === 'bad'" class="st-ai" data-slop>
                    <WandSparkles :size="12" :stroke-width="2" />
                    Ask AI
                    <Sparkles :size="11" :stroke-width="2" />
                  </span>
                  <span v-else class="st-ai">Explain failure</span>
                </template>
                <span v-else class="st-time">
                  {{ faultFor(good, lesson.id) === 'style-caps' ? d.time.toUpperCase() : d.time }}
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
