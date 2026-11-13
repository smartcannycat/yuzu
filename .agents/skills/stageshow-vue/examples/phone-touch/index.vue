<script setup lang="ts">
import { Stage, Phone, Expand, Bar, Avatar, Icon, Meter, Roll, States, type Act } from '../../kit'
import './fitness.css'

// Two of the cards in view say what they are; the rest are art with bars
const CARD_NAMES: Record<number, string> = { 0: 'Morning Ride', 2: 'Hill Repeats' }

// A fitness app's landing-page demo, phone only. Story in three beats:
// the Workouts list (context), a tap on "Tempo Run" expands its card into the
// workout detail the way iOS cards open (action), then Start sets the timer
// running (result). It loops by being put back: pause, close, and the card
// folds back into its place in the list, so no frame is ever empty.
//
// The expanded detail is the same element as the card in the list: closed, it
// is clipped to the card's rect and its header art is slid down so only the
// bottom of the art (title and duration) shows; open, the clip and the slide
// release together. Nothing swaps, so there is no seam at the hand-over.
//
// Real strings: Workouts, Tempo Run, 32 min, Start/Pause/Resume, Warm up,
// the timer. Everything else is a line or a shape.

type Phase = 'idle' | 'running' | 'paused'
type S = { open: boolean; phase: Phase; t: number }

const START: S = { open: false, phase: 'idle', t: 0 }

// The card has equal screen-point gutters; Expand measures the current Phone.
const CARD = { x: 16, h: 132 }
const TOPS = [150, 296, 442, 588]
const PICK = 1
const REST = { x: 200, y: 300 }
const HEADER = 300

const ART = ['fx-art--sage', 'fx-art--tempo', 'fx-art--slate', 'fx-art--sand']
const LIST_TEXT = [
  { eyebrow: 38, title: 128, sub: 44 },
  null,
  { eyebrow: 46, title: 104, sub: 52 },
  { eyebrow: 34, title: 140, sub: 40 },
]

const time = (t: number) => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`

const script = async (a: Act<S>) => {
  await a.wait(1100)
  a.mark('tap')
  await a.click('card')
  a.put({ open: true })
  await a.wait(1400)
  a.mark('start')
  await a.click('start')
  a.put({ phase: 'running' })
  for (let i = 0; i < 6; i++) {
    await a.wait(1000)
    a.put((s) => ({ t: s.t + 1 }))
  }
  await a.wait(400)
  a.mark('pause')
  await a.click('start')
  a.put({ phase: 'paused' })
  await a.wait(1100)
  a.mark('close')
  await a.click('close')
  a.put({ open: false })
  await a.wait(900)
  // Hidden behind the card's clip now: reset the workout unseen
  await a.snap({ phase: 'idle', t: 0 })
  // The finger lifts away; the touch style shows nothing between taps
  await a.move(REST)
  await a.wait(300)
}
</script>

<template>
  <Stage
    :width="400"
    :height="520"
    :compact="{ below: 400, width: 358, height: 520 }"
    :initial="START"
    :poster="{ open: true, phase: 'running', t: 7 }"
    :script="script"
    :cursor="{ at: REST, style: 'touch' }"
    class="fx"
    v-slot="{ state: s, rect, layout }"
  >
    <div class="fx-wash" />
    <Phone :width="layout === 'compact' ? 326 : 300" class="fx-phone" :data-open="s.open || undefined">
      <div class="fx-list" :data-back="s.open || undefined">
        <header class="fx-head">
          <Bar :w="96" :h="8" :r="4" :tone="3" />
          <div class="fx-head__row">
            <span class="fx-title">Workouts</span>
            <Avatar name="Maya" :size="36" />
          </div>
        </header>
        <template v-for="(y, i) in TOPS" :key="i">
          <span v-if="i === PICK" class="fx-slot" data-target="card" :style="{ top: `${y}px` }" />
          <div v-else :class="`fx-card ${ART[i]}`" :style="{ top: `${y}px` }">
            <span class="fx-card__text">
              <span class="fx-line" :style="{ width: `${LIST_TEXT[i]!.eyebrow}px`, height: '7px', opacity: 0.55 }" />
              <span v-if="CARD_NAMES[i]" class="fx-card__title">{{ CARD_NAMES[i] }}</span>
              <span v-else class="fx-line" :style="{ width: `${LIST_TEXT[i]!.title}px`, height: '13px' }" />
              <span class="fx-line" :style="{ width: `${LIST_TEXT[i]!.sub}px`, height: '7px', opacity: 0.55 }" />
            </span>
          </div>
        </template>
        <nav class="fx-tabs">
          <span v-for="i in [0, 1, 2, 3]" :key="i" class="fx-tab" :data-on="i === 0 || undefined">
            <span class="fx-tab__icon" />
            <span class="fx-tab__label" />
          </span>
        </nav>
      </div>

      <!-- The picked card and its detail are one element -->
      <div class="fx-press" :style="{ transformOrigin: `50% ${TOPS[PICK]! + CARD.h / 2}px` }">
        <Expand
          class="fx-detail"
          :open="s.open"
          :from="rect('card')"
          :radius="22"
          :duration="620"
        >
          <div class="fx-detail__inner" :style="{ transform: `translateY(${s.open ? 0 : CARD.h - HEADER}px)` }">
            <div
              :class="`fx-hero ${ART[PICK]}`"
              :style="{
                clipPath: s.open
                  ? 'inset(0px 0px 0px 0px round 0px 0px 0px 0px)'
                  : `inset(0px ${CARD.x}px 0px ${CARD.x}px round 0px 0px 22px 22px)`,
              }"
            >
              <span class="fx-close" data-target="close">
                <Icon name="close" :size="14" :stroke="2" />
              </span>
              <span class="fx-hero__text" :style="{ transform: `translateX(${s.open ? 0 : CARD.x}px)` }">
                <span class="fx-hero__eyebrow" />
                <span class="fx-hero__title">Tempo Run</span>
                <span class="fx-hero__sub">32 min</span>
              </span>
            </div>
            <div class="fx-body">
              <div class="fx-panel">
                <div class="fx-about" :data-hide="s.phase !== 'idle' || undefined">
                  <div class="fx-stats">
                    <span
                      v-for="([l, v], i) in [[34, 46], [40, 30], [28, 38]]"
                      :key="i"
                      class="fx-stat"
                    >
                      <Bar :w="l" :h="6" :r="3" :tone="3" />
                      <Bar :w="v" :h="11" :r="4" :tone="5" />
                    </span>
                  </div>
                  <div class="fx-desc">
                    <Bar w="92%" :h="7" :r="3" :tone="2" />
                    <Bar w="84%" :h="7" :r="3" :tone="2" />
                    <Bar w="58%" :h="7" :r="3" :tone="2" />
                  </div>
                </div>
                <div class="fx-timer" :data-show="s.phase !== 'idle' || undefined">
                  <span class="fx-timer__label">Warm up</span>
                  <span class="fx-timer__time" :data-paused="s.phase === 'paused' || undefined">
                    <Roll>{{ time(s.t) }}</Roll>
                  </span>
                  <Meter :value="s.t / 40" class="fx-meter" />
                </div>
              </div>
              <span class="fx-start" data-target="start" :data-phase="s.phase">
                <States :value="s.phase">
                  <template #idle>
                    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                      <path d="M4.5 2.9v10.2a.9.9 0 0 0 1.37.77l8.2-5.1a.9.9 0 0 0 0-1.54l-8.2-5.1A.9.9 0 0 0 4.5 2.9Z" fill="currentColor" />
                    </svg>
                    Start
                  </template>
                  <template #running>
                    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                      <rect x="3.5" y="2.5" width="3.2" height="11" rx="1" fill="currentColor" />
                      <rect x="9.3" y="2.5" width="3.2" height="11" rx="1" fill="currentColor" />
                    </svg>
                    Pause
                  </template>
                  <template #paused>
                    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
                      <path d="M4.5 2.9v10.2a.9.9 0 0 0 1.37.77l8.2-5.1a.9.9 0 0 0 0-1.54l-8.2-5.1A.9.9 0 0 0 4.5 2.9Z" fill="currentColor" />
                    </svg>
                    Resume
                  </template>
                </States>
              </span>
              <div class="fx-intervals">
                <Bar :w="72" :h="8" :r="4" :tone="4" />
                <span v-for="(w, i) in [86, 64, 92]" :key="i" class="fx-interval">
                  <span class="fx-interval__dot" :data-i="i" />
                  <Bar :w="w" :h="8" :r="4" :tone="3" />
                  <Bar :w="30" :h="8" :r="4" :tone="2" />
                </span>
              </div>
            </div>
          </div>
        </Expand>
      </div>
    </Phone>
  </Stage>
</template>
