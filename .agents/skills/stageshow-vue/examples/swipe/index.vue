<script setup lang="ts">
import { Archive, ChevronLeft, ChevronRight, Ellipsis, Megaphone, MessageSquare, ShoppingCart, User } from 'lucide-vue-next'
import { Avatar, Bar, Collapse, Phone, Row, Stage, type Act, type Rect } from '../../kit'
import './swipe.css'

// A mail app's swipe to archive, phone only. Beats: the finger presses a
// message, swipes it left with the archive action opening behind, lets go,
// and the row carries on off the screen at the speed the finger left it;
// then the gap closes and the next message moves up. Plays once; Replay is
// the reset.
//
// What makes the swipe read as one gesture, rather than harsh, paused half
// way or jolted into place:
// - The row is under the finger the whole way, 1:1, no lag, no rubber band.
// - The throw starts at the finger's own speed. The script measures the last
//   few samples of the drag and builds a curve whose first slope is that
//   speed, so there is no step at the hand-over and no pause.
// - The Archive mark rides the row's trailing edge, so it ends at the left
//   edge when the row is off, as Mail's does; the gap then closes in one ease
//   with the color solid, never fading through gray.
// - The kit's touch cursor presses first, then swipes, leaving its trail.
//
// Only the swiped message is unread: a blue dot on a placeholder row would
// be the heaviest mark on filler.
//
// Real strings: Inbox, Edit, the swiped message, the one that moves up into
// its place (so the last frame has words where the eye lands), Archive. The other rows are
// placeholder lines at a real message's line heights.

type S = { dx: number; throw: { ms: number; ease: string } | null; gone: boolean }

const initial: S = { dx: 0, throw: null, gone: false }
const poster: S = { dx: 0, throw: null, gone: true }

const PICK = 0

const MAIL = [
  { from: 'Northwind Air', time: '9:12', subject: 'Your trip to Lisbon', preview: 'Check-in opens 24 hours before departure. Your seat is 14A.', unread: true },
  { from: 'Jon Park', time: '8:30', subject: 'Re: pricing page', preview: 'Looks good to me. One note on the annual toggle copy.', unread: false },
  { from: 'Maya Chen', time: '9:41', subject: 'Launch checklist', preview: 'Two things left before Thursday: the pricing page and the press kit.', unread: false },
  { from: 'Ana Ruiz', time: 'Yesterday', subject: 'Q3 board deck', preview: 'Draft is in the shared folder, comments welcome by Friday.', unread: false },
  { from: 'Leo Sato', time: 'Yesterday', subject: 'Offsite dates', preview: 'Can everyone do the week of the 14th? Venue is holding it.', unread: false },
]

// Placeholder rows: bars at a real message's line heights, so every row is
// the height a real one would be. Only the swiped message has words.
const FILL = [
  null,
  null,
  { from: 104, subject: 148, preview: [250, 170] },
  { from: 92, subject: 136, preview: [256, 180] },
  { from: 84, subject: 112, preview: [230, 140] },
]

async function script(a: Act<S>) {
  await a.wait(900)

  // 1. Press the message on its right side, then swipe it left
  a.mark('swipe')
  const row = a.rect('row')
  const y = row.y + row.height * 0.5
  await a.move({ x: row.x + row.width * 0.8, y })
  await a.wait(250)
  const from = row.x + row.width * 0.8
  const samples: { x: number; t: number }[] = []
  await a.drag(
    { x: row.x + row.width * 0.22, y },
    (at) => {
      samples.push({ x: at.x, t: performance.now() })
      a.put({ dx: at.x - from })
    },
    // A swipe is flat: no carrying bow, the finger runs along the row
    { duration: 300, path: (t, a0, b0) => ({ x: a0.x + (b0.x - a0.x) * t, y: a0.y }) },
  )

  // 2. The finger lifts still moving; the row carries on at that speed
  a.mark('throw')
  const last = samples.slice(-4)
  const v = last.length > 1 ? Math.abs(last[last.length - 1]!.x - last[0]!.x) / Math.max(1, last[last.length - 1]!.t - last[0]!.t) : 1
  const dx = samples.length ? samples[samples.length - 1]!.x - from : 0
  const left = row.width + dx
  const ms = 300
  // A curve whose first slope is the finger's speed, easing out at the end
  const x1 = 0.25
  const y1 = Math.min(0.95, (x1 * v * ms) / left)
  a.put({ throw: { ms, ease: `cubic-bezier(${x1}, ${y1.toFixed(3)}, 0.35, 1)` }, dx: -row.width })
  await a.wait(ms)

  // 3. The gap closes and the next message moves up
  a.mark('close')
  a.put({ gone: true })
  await a.wait(1800)
  a.mark('done')
}

function rowShift(s: S, rect: (name: string) => Rect) {
  const box = rect('row')
  const k = box.width ? box.width / 402 : 1
  return s.dx / k
}

function openWidth(s: S, rect: (name: string) => Rect) {
  return Math.max(0, -rowShift(s, rect))
}
</script>

<template>
  <Stage
    :width="400"
    :height="480"
    :compact="{ below: 400, width: 358, height: 480 }"
    :initial="initial"
    :poster="poster"
    :script="script"
    play="once"
    :cursor="{ at: { x: 330, y: 470 }, style: 'touch' }"
    class="sw"
    v-slot="{ state: s, rect, layout }"
  >
    <Phone :width="layout === 'compact' ? 340 : 380" class="sw-phone">
      <div class="sw-app">
        <header class="sw-head">
          <div class="sw-bar-top">
            <span class="sw-round"><ChevronLeft :size="20" :stroke-width="2.25" /></span>
            <span class="sw-round"><Ellipsis :size="18" :stroke-width="2.25" /></span>
          </div>
          <div class="sw-title">Inbox</div>
          <div class="sw-cats">
            <span class="sw-cat" data-on>
              <User :size="15" :stroke-width="2.25" />
              Primary
            </span>
            <span class="sw-cat"><ShoppingCart :size="16" :stroke-width="2" /></span>
            <span class="sw-cat"><Megaphone :size="16" :stroke-width="2" /></span>
            <span class="sw-cat"><MessageSquare :size="16" :stroke-width="2" /></span>
          </div>
        </header>
        <div class="sw-list">
          <component
            :is="i === PICK ? Collapse : 'div'"
            v-for="(m, i) in MAIL"
            :key="m.from"
            v-bind="i === PICK ? { open: !s.gone, solid: true } : {}"
          >
            <div class="sw-cell" :data-target="i === PICK ? 'row' : undefined">
              <!-- Only while the row is off its rest: at rest its antialiased edges would show a purple hairline -->
              <div v-if="i === PICK && (s.dx !== 0 || s.throw)" class="sw-action" />
              <Row
                :pad="0"
                class="sw-row"
                :unread="m.unread"
                :style="
                  i === PICK
                    ? {
                        transform: `translateX(${rowShift(s, rect)}px)`,
                        transition: s.throw ? `transform ${s.throw.ms}ms ${s.throw.ease}` : 'none',
                      }
                    : undefined
                "
              >
                <template #lead>
                  <Avatar v-if="i === PICK || i === PICK + 1" :name="m.from" tone="ios" :size="40" />
                  <Avatar v-else :size="40" />
                </template>
                <template #title>
                  <template v-if="i === PICK || i === PICK + 1">{{ m.from }}</template>
                  <Bar v-else :w="FILL[i]!.from" :h="11" :r="5.5" :tone="4" />
                </template>
                <template #meta>
                  <span v-if="i === PICK || i === PICK + 1" class="sw-time">
                    {{ m.time }}
                    <ChevronRight :size="14" :stroke-width="2.25" />
                  </span>
                  <Bar v-else :w="34" :h="9" :r="4.5" :tone="2" />
                </template>
                <template #subtitle>
                  <span v-if="i === PICK || i === PICK + 1" class="sw-subject">{{ m.subject }}</span>
                  <Bar v-else :w="FILL[i]!.subject" :h="9" :r="4.5" :tone="3" />
                </template>
                <template #preview>
                  <template v-if="i === PICK || i === PICK + 1">{{ m.preview }}</template>
                  <span v-else v-for="(w, j) in FILL[i]!.preview" :key="j" class="sw-fill">
                    <Bar :w="w" :h="9" :r="4.5" :tone="2" />
                  </span>
                </template>
                <span
                  v-if="i === PICK"
                  class="sw-action__mark"
                  :style="{
                    opacity: s.gone ? 0 : Math.min(1, openWidth(s, rect) / 60),
                    transition: s.gone ? 'opacity 120ms ease-out' : 'none',
                  }"
                >
                  <Archive :size="22" :stroke-width="2" />
                  Archive
                </span>
              </Row>
            </div>
          </component>
        </div>
      </div>
    </Phone>
  </Stage>
</template>
