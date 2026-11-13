<script lang="ts">
export const detailLessons = [
  { id: 'detail-throw', title: 'Throw a swipe at the finger’s speed', note: 'The same row swiped left. Released, it should carry on at the speed the finger left it and the gap should close in one ease. A pause at the hand-over, an ease-in from rest or a gap that snaps shut each reads as harsh. See examples/swipe.', bad: 'Pauses at release, eases in from rest, gap snaps shut', good: 'Leaves at the finger’s speed, gap closes in one ease', motion: true },
  { id: 'detail-reaction', title: 'Draw a reaction as the app does', note: 'The same message getting a reaction. A drawn glyph in a disc over the bubble’s words, appearing in one frame, reads as made up. Use the real emoji in a small pill on the bubble’s lower corner, ringed in the ground so it sits on the edge, scaling in from the corner it hangs from.', bad: 'A drawn heart in a disc, over the words, in one frame', good: 'The emoji in a pill on the corner, scaling in', motion: true },
  { id: 'detail-chart', title: 'Draw a chart on from its start', note: 'The same revenue line arriving. Faded in whole, the line, area and end dot arrive as one flat picture and the trend is never seen. Draw the line left to right, let the area follow under it, and land the end dot when the line reaches it.', bad: 'Line, area and dot fade in together', good: 'Line draws on, area follows, dot lands last', motion: true },
  { id: 'detail-bar', title: 'Balance a top bar', note: 'The same inbox. A bar with one control and an empty side reads as unfinished. Give it what the product puts there: Mail has a back button on the left. If the product has nothing, drop the bar rather than leave half of it.', bad: 'Only the more button, the left side empty', good: 'Back on the left, more on the right' },
  { id: 'detail-copy', title: 'Choose copy that fits', note: 'The same invite. An email that truncates in its chip, a name that wraps and labels of uneven length make the scene look broken. Unless the brief fixes them, pick names, emails and values whose length suits the layout.', bad: 'Truncated email, wrapped name, ragged labels', good: 'Short real names and an email that fits' },
  { id: 'detail-pin', title: 'Pin a changing label to its icon', note: 'The same role picker as its value changes. A picker at the end of a row is anchored at its chevron: the label sits against it and grows away from it, so the chevron never moves and the gap never changes. Held in a fixed slot instead, the label starts at the slot’s left and the space before the chevron grows and shrinks with every value.', bad: 'Label at the slot’s left, the gap to the chevron changing', good: 'Label against the chevron, growing left', motion: true },
] as const

type Id = (typeof detailLessons)[number]['id']
</script>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { ChevronDown, ChevronLeft, Ellipsis } from 'lucide-vue-next'
import { Stage, type Act } from '../kit'
import './details.css'

const props = defineProps<{
  lessonId: string
}>()

type S = { phase: number; role: number }

const ROLES = ['Can view', 'Can edit', 'Full access']

async function throwScript(a: Act<S>) {
  await a.wait(700)
  a.put({ phase: 1 }) // the drag
  await a.wait(320)
  a.put({ phase: 2 }) // released
  await a.wait(700)
  a.put({ phase: 3 }) // gap closes
  await a.wait(1800)
  a.snap({ phase: 0 })
}

async function stepScript(a: Act<S>) {
  await a.wait(800)
  a.put({ phase: 1 })
  await a.wait(2600)
  a.snap({ phase: 0 })
}

async function roleScript(a: Act<S>) {
  for (let i = 1; i <= ROLES.length; i++) {
    await a.wait(1300)
    a.put({ role: i % ROLES.length })
  }
}

const SCRIPT: Partial<Record<Id, (a: Act<S>) => Promise<void>>> = {
  'detail-throw': throwScript,
  'detail-reaction': stepScript,
  'detail-chart': stepScript,
  'detail-pin': roleScript,
}

const POINTS = [62, 58, 64, 55, 60, 48, 52, 40, 44, 34, 38, 26, 30, 18]
const LINE = POINTS.map((y, i) => `${i ? 'L' : 'M'}${8 + i * 20},${y}`).join(' ')
const AREA = `${LINE} L${8 + 13 * 20},86 L8,86 Z`

// An emoji centered by its drawing, not its glyph box. Emoji fonts pad the
// glyph unevenly (Apple's sits off center in its box), by an amount that
// changes with the size and the screen. So the emoji is drawn to a canvas,
// cropped to its ink, and the crop is what the pill centers
const Emoji = defineComponent({
  props: {
    char: { type: String, required: true },
    size: { type: Number, default: 15 },
  },
  setup(p) {
    const canvasRef = ref<HTMLCanvasElement | null>(null)
    const box = ref<[number, number]>([p.size, p.size])

    function draw() {
      const out = canvasRef.value
      if (!out) return
      const k = Math.max(2, Math.ceil(devicePixelRatio)) * 2
      const n = Math.ceil(p.size * 2 * k)
      const c = document.createElement('canvas')
      c.width = c.height = n
      const g = c.getContext('2d', { willReadFrequently: true })
      if (!g) return
      g.font = `${p.size * k}px ${getComputedStyle(out).fontFamily}`
      g.textAlign = 'center'
      g.textBaseline = 'middle'
      g.fillText(p.char, n / 2, n / 2)
      const { data } = g.getImageData(0, 0, n, n)
      let x0 = n,
        x1 = -1,
        y0 = n,
        y1 = -1
      for (let y = 0; y < n; y++) {
        for (let x = 0; x < n; x++) {
          if (data[(y * n + x) * 4 + 3]! > 8) {
            if (x < x0) x0 = x
            if (x > x1) x1 = x
            if (y < y0) y0 = y
            if (y > y1) y1 = y
          }
        }
      }
      if (x1 < 0) return
      const w = x1 - x0 + 1,
        hPx = y1 - y0 + 1
      out.width = w
      out.height = hPx
      out.getContext('2d')!.drawImage(c, x0, y0, w, hPx, 0, 0, w, hPx)
      const side = Math.round(Math.max(w, hPx) / k / 2) * 2
      box.value = [side * (w / Math.max(w, hPx)), side * (hPx / Math.max(w, hPx))]
    }

    onMounted(draw)
    watch(() => [p.char, p.size], draw)

    return () =>
      h('canvas', {
        ref: canvasRef,
        class: 'dr-emoji',
        role: 'img',
        'aria-label': p.char,
        style: { width: `${box.value[0]}px`, height: `${box.value[1]}px` },
      })
  },
})

const revision = ref(0)
const lesson = computed(() => detailLessons.find((item) => item.id === props.lessonId))
const id = computed(() => lesson.value?.id as Id | undefined)
const script = computed(() => (id.value ? SCRIPT[id.value] : undefined))
const height = 252

const COPY_GOOD = [
  ['Jon Park', 'Owner'],
  ['Ana Ruiz', 'Editor'],
] as const
const COPY_BAD = [
  ['Bartholomew Featherstonehaugh', 'Owner'],
  ['Al', 'Editor with comment access'],
] as const
</script>

<template>
  <section v-if="lesson && id" class="cp-lesson">
    <header>
      <div>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.note }}</p>
      </div>
      <button v-if="script" class="tc-replay" type="button" @click="revision++">Replay pair</button>
    </header>
    <Stage
      :key="`${id}-${revision}`"
      :width="704"
      :height="height + 50"
      :compact="{ below: 704, width: 340, height: height * 2 + 116 }"
      :initial="{ phase: 0, role: 0 }"
      :poster="{ phase: 1, role: 0 }"
      :script="script"
      class="tc-stage"
      v-slot="{ state: s }"
    >
      <div class="tc-pair dd-pair">
        <figure v-for="good in [false, true]" :key="String(good)">
          <div class="tc-visual dd-visual">
            <!-- detail-throw -->
            <div v-if="id === 'detail-throw'" class="dt-list" :data-phase="s.phase" :data-good="good || undefined">
              <div class="dt-slot">
                <div class="dt-action">Archive</div>
                <div class="dt-row">
                  <span class="dt-av">N</span>
                  <span class="dt-lines"><b>Northwind Air</b><span>Your trip to Lisbon</span></span>
                </div>
              </div>
              <div class="dt-row dt-row--next">
                <span class="dt-av dt-av--jp">J</span>
                <span class="dt-lines"><b>Jon Park</b><span>Re: pricing page</span></span>
              </div>
              <div class="dt-row dt-row--fill">
                <span class="dt-av dt-av--fill" />
                <span class="dt-lines">
                  <i :style="{ width: '92px' }" />
                  <i :style="{ width: '140px' }" />
                </span>
              </div>
            </div>

            <!-- detail-reaction -->
            <div v-else-if="id === 'detail-reaction'" class="dr-thread" :data-on="s.phase || undefined" :data-good="good || undefined">
              <div class="dr-bubble dr-bubble--them">Landed! The view from the hotel is unreal</div>
              <div class="dr-bubble dr-bubble--me">
                Send photos
                <span v-if="good" class="dr-pill"><Emoji char="😍" /></span>
                <span v-else class="dr-disc">
                  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                    <path d="M6 10.2 1.6 6A2.6 2.6 0 0 1 6 2.6 2.6 2.6 0 0 1 10.4 6Z" fill="#fff" />
                  </svg>
                </span>
              </div>
            </div>

            <!-- detail-chart -->
            <div v-else-if="id === 'detail-chart'" class="dc-card" :data-on="s.phase || undefined" :data-good="good || undefined">
              <span class="dc-label">Revenue, 14 days</span>
              <span class="dc-value">$68,200</span>
              <svg class="dc-svg" width="276" height="90" viewBox="0 0 276 90" aria-hidden="true">
                <defs>
                  <linearGradient :id="`dc-fill-${good}`" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0" stop-color="#3b82f6" stop-opacity=".18" />
                    <stop offset="1" stop-color="#3b82f6" stop-opacity="0" />
                  </linearGradient>
                  <clipPath :id="`dc-clip-${good}`">
                    <rect class="dc-wipe" x="0" y="0" width="276" height="90" />
                  </clipPath>
                </defs>
                <path
                  class="dc-area"
                  :d="AREA"
                  :fill="`url(#dc-fill-${good})`"
                  :clip-path="good ? `url(#dc-clip-${good})` : undefined"
                />
                <path
                  class="dc-line"
                  :d="LINE"
                  pathLength="1"
                  fill="none"
                  stroke="#3b82f6"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
                <circle class="dc-dot" :cx="8 + 13 * 20" :cy="18" r="3.5" fill="#3b82f6" stroke="#fff" stroke-width="1.5" />
              </svg>
            </div>

            <!-- detail-bar -->
            <div v-else-if="id === 'detail-bar'" class="db-screen">
              <div class="db-top">
                <span v-if="good" class="db-round"><ChevronLeft :size="18" :stroke-width="2.25" /></span>
                <span v-else />
                <span class="db-round"><Ellipsis :size="16" :stroke-width="2.25" /></span>
              </div>
              <div class="db-title">Inbox</div>
              <div v-for="i in [0, 1]" :key="i" class="dt-row dt-row--fill">
                <span class="dt-av dt-av--fill" />
                <span class="dt-lines">
                  <i :style="{ width: `${[96, 80][i]}px` }" />
                  <i :style="{ width: `${[150, 128][i]}px` }" />
                </span>
              </div>
            </div>

            <!-- detail-copy -->
            <div v-else-if="id === 'detail-copy'" class="dy-card">
              <div class="dy-field">
                <span class="dy-chip">{{ good ? 'maya@northwind.com' : 'alexandra.whitfield@northwindlabs.com' }}</span>
              </div>
              <div class="dy-people">
                <div v-for="[n, r] in (good ? COPY_GOOD : COPY_BAD)" :key="n" class="dy-person">
                  <span class="dt-av dt-av--fill" />
                  <span class="dy-name">{{ n }}</span>
                  <span class="dy-role">{{ r }}</span>
                </div>
              </div>
            </div>

            <!-- detail-pin -->
            <div v-else class="dp-row">
              <span class="dp-who"><span class="dt-av dt-av--jp">J</span>Jon Park</span>
              <span class="dp-select" :data-good="good || undefined">
                <span class="dp-labels">
                  <span v-for="(r, i) in ROLES" :key="r" class="dp-label" :data-on="i === s.role || undefined">
                    {{ r }}
                  </span>
                </span>
                <ChevronDown :size="14" :stroke-width="2" />
              </span>
            </div>
          </div>
          <figcaption>{{ good ? lesson.good : lesson.bad }}</figcaption>
        </figure>
      </div>
    </Stage>
  </section>
</template>
