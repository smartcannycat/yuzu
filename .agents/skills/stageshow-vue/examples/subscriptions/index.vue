<script setup lang="ts">
import { Avatar, Bar, Chart, Collapse, Count, Fly, Roll, Spinner, Stage, States, Window, type Act, type Rect } from '../../kit'
import './subs.css'

// A system story, no cursor. A customer subscribes on a checkout, the price
// rides into the company's billing dashboard as the new row's amount, and MRR
// rolls up. It happens twice, then the scene changes to a second company and
// happens once more: a different business on the same product, which is also
// how the loop resets without rewinding. The checkout and the window are the
// two places; the chip is the only thing that travels between them.

type Pulse = { name: string; initial: string; plan: string; price: number }
type Scene = { org: string; tile: string; mrr: number; history: number[]; pulses: Pulse[] }

const SCENES: Scene[] = [
  {
    org: 'Northwind',
    tile: 'N',
    mrr: 48210,
    history: [31, 33, 32, 36, 38, 37, 41, 44, 43, 46, 48.2],
    pulses: [
      { name: 'Maya Lin', initial: 'M', plan: 'Pro', price: 49 },
      { name: 'Studio Kite', initial: 'S', plan: 'Team', price: 99 },
    ],
  },
  {
    org: 'Brightside',
    tile: 'B',
    mrr: 12480,
    history: [6, 6.4, 7.1, 7, 8.2, 8.8, 9.1, 10.4, 10.9, 11.6, 12.48],
    pulses: [{ name: 'Leo Park', initial: 'L', plan: 'Plus', price: 29 }],
  },
]

// Filler rows that were there before the story: they keep their place below
const OLD = [
  { name: 62, amount: 34 },
  { name: 78, amount: 40 },
  { name: 54, amount: 34 },
  { name: 70, amount: 40 },
]

const NAV_WIDTHS = [46, 58, 40, 52]

type Pay = 'idle' | 'busy' | 'paid' | 'done'
type S = {
  scene: number
  // per scene: rows opened, rows landed, which pulse the checkout shows, its button
  open: [number, number]
  landed: [number, number]
  k: [number, number]
  pay: [Pay, Pay]
  fly: null | { scene: number; i: number; from: Rect; to: Rect; go: boolean }
}

const START: S = { scene: 0, open: [0, 0], landed: [0, 0], k: [0, 0], pay: ['idle', 'idle'], fly: null }
const POSTER: S = { ...START, open: [2, 0], landed: [2, 0], k: [1, 0], pay: ['done', 'idle'] }

const money = (n: number) => '$' + Math.round(n).toLocaleString('en-US')
const set2 = <T,>(pair: [T, T], i: number, v: T): [T, T] => (i === 0 ? [v, pair[1]] : [pair[0], v])

async function pulse(a: Act<S>, sc: number, i: number) {
  await a.set((s) => ({ pay: set2(s.pay, sc, 'busy') }))
  await a.wait(700)
  // Paid: the chip lifts off the button at once and the new row's space opens
  // under it while it travels. Where it lands is the top of the list as it is
  // now (the new row opens there), at the right edge where amounts sit.
  const list = a.rect(`list-${sc}`, { layout: true })
  const row = a.rect(`row-${sc}-${i}`, { layout: true })
  const pill = a.rect(`pill-${sc}-${i}`, { layout: true })
  const b = a.rect(`pay-${sc}`, { layout: true })
  const size = { width: pill.width, height: pill.height }
  // The row keeps its full layout height inside Collapse. Measure the pill's
  // actual inset, including the row's border, so the handoff has no half-pixel hop.
  const to = { ...pill, y: list.y + pill.y - row.y }
  const from = { x: b.x + b.width / 2 - pill.width / 2, y: b.y + b.height / 2 - pill.height / 2, ...size }
  await a.set((s) => ({ pay: set2(s.pay, sc, 'paid'), fly: { scene: sc, i, from, to, go: false } }))
  // The chip buds off the button before it sets off
  await a.wait(200)
  await a.set((s) => ({ open: set2(s.open, sc, i + 1), fly: { ...s.fly!, go: true } }))
  await a.wait(900)
  // Landed: the real pill takes over in the same frame the chip goes
  await a.set((s) => ({ fly: null, landed: set2(s.landed, sc, i + 1), pay: set2(s.pay, sc, 'done') }))
}

async function script(a: Act<S>) {
  await a.wait(900)
  a.mark('first')
  await pulse(a, 0, 0)
  await a.wait(700)
  // The checkout moves on to the next customer: only the plan and price change
  await a.set((s) => ({ pay: set2(s.pay, 0, 'idle'), k: set2(s.k, 0, 1) }))
  await a.wait(1000)
  a.mark('second')
  await pulse(a, 0, 1)
  await a.wait(2000)

  a.mark('scene')
  await a.set({ scene: 1 })
  await a.wait(700)
  // Northwind resets while it's out of sight
  await a.snap((s) => ({ open: set2(s.open, 0, 0), landed: set2(s.landed, 0, 0), k: set2(s.k, 0, 0), pay: set2(s.pay, 0, 'idle') }))
  await a.wait(500)
  await pulse(a, 1, 0)
  await a.wait(2000)

  await a.set({ scene: 0 })
  await a.wait(700)
  await a.snap((s) => ({ open: set2(s.open, 1, 0), landed: set2(s.landed, 1, 0), pay: set2(s.pay, 1, 'idle') }))
  await a.wait(300)
}

function sceneMrr(sc: number, s: S) {
  const scene = SCENES[sc]
  const added = scene.pulses.slice(0, s.landed[sc]).reduce((t, p) => t + p.price, 0)
  return scene.mrr + added
}

function sceneData(sc: number, s: S) {
  const scene = SCENES[sc]
  const mrr = sceneMrr(sc, s)
  return [...scene.history.slice(0, -1), mrr / 1000]
}

function reversedPulses(sc: number) {
  return SCENES[sc].pulses.map((p, i) => ({ p, i })).reverse()
}
</script>

<template>
  <Stage
    :width="720"
    :height="440"
    :compact="{ below: 600, width: 358, height: 460 }"
    :initial="START"
    :poster="POSTER"
    :script="script"
    class="sb"
    v-slot="{ state: s, layout }"
  >
    <div class="sb-wash" />
    <Window url="dashboard.tally.com/subscriptions" class="sb-window">
      <div class="sb-scenes">
        <div
          v-for="sc in [0, 1]"
          :key="sc"
          class="sb-scene"
          :data-on="s.scene === sc || undefined"
          :aria-hidden="s.scene !== sc || undefined"
        >
          <aside class="sb-side">
            <div class="sb-org">
              <span class="sb-tile" :data-scene="sc">
                {{ SCENES[sc].tile }}
              </span>
              <span class="sb-strong">{{ SCENES[sc].org }}</span>
            </div>
            <div v-for="(w, i) in NAV_WIDTHS" :key="i" class="sb-nav" :data-on="i === 1 || undefined">
              <Bar :w="10" :h="10" :r="3" :tone="i === 1 ? 4 : 3" />
              <Bar :w="w" :h="5" :tone="i === 1 ? 4 : 2" />
            </div>
          </aside>
          <main class="sb-main">
            <div class="sb-head">
              <span class="sb-title">
                <!-- Compact drops the sidebar, so the company moves up beside the title -->
                <span class="sb-tile sb-head-tile" :data-scene="sc">
                  {{ SCENES[sc].tile }}
                </span>
                Subscriptions
              </span>
              <Bar :w="56" :h="22" :r="6" :tone="2" />
            </div>
            <div class="sb-mrr">
              <div class="sb-mrr__text">
                <span class="sb-muted">MRR</span>
                <Count class="sb-mrr__value" :value="sceneMrr(sc, s)" :duration="900" :format="money" />
              </div>
              <Chart :data="sceneData(sc, s)" :width="layout === 'compact' ? 110 : 190" :height="52" class="sb-chart" />
            </div>
            <div class="sb-list" :data-target="`list-${sc}`">
              <!-- Newest first: each new subscriber opens at the top and pushes the rest down -->
              <Collapse
                v-for="{ p, i } in reversedPulses(sc)"
                :key="p.name"
                :open="s.open[sc] > i"
                reveal="clip"
              >
                <div class="sb-row" :data-target="`row-${sc}-${i}`" :data-landed="s.landed[sc] > i || undefined">
                  <Avatar :name="p.name" :size="22" class="sb-av" :data-scene="sc" :data-i="i" :style="{ background: undefined, color: undefined }" />
                  <span class="sb-name">{{ p.name }}</span>
                  <span class="sb-plan">{{ p.plan }}</span>
                  <span class="sb-pill" :data-target="`pill-${sc}-${i}`">
                    +${{ p.price }}
                  </span>
                </div>
              </Collapse>
              <div v-for="(r, i) in OLD" :key="i" class="sb-row sb-row--old">
                <Bar :w="22" :h="22" :r="11" :tone="2" />
                <Bar :w="r.name" :h="5" :tone="3" />
                <Bar :w="r.amount" :h="5" :tone="2" style="margin-left: auto" />
              </div>
            </div>
          </main>
        </div>
      </div>
    </Window>

    <section
      v-for="sc in [0, 1]"
      :key="sc"
      class="sb-checkout"
      :data-in="s.scene === sc || undefined"
    >
      <div class="sb-checkout__head">
        <span class="sb-tile" :data-scene="sc">
          {{ SCENES[sc].tile }}
        </span>
        <span class="sb-strong">
          {{ SCENES[sc].org }} <Roll variant="fade">{{ SCENES[sc].pulses[s.k[sc]].plan }}</Roll>
        </span>
      </div>
      <div class="sb-price">
        <Roll>{{ `$${SCENES[sc].pulses[s.k[sc]].price}` }}</Roll>
        <span class="sb-muted">per month</span>
      </div>
      <div class="sb-fields">
        <div class="sb-field">
          <Bar :w="sc === 0 ? 96 : 82" :h="5" :tone="3" />
        </div>
        <div class="sb-field">
          <Bar :w="22" :h="12" :r="3" :tone="2" />
          <Bar :w="70" :h="5" :tone="3" />
        </div>
      </div>
      <div class="sb-pay" :data-target="`pay-${sc}`" :data-state="s.pay[sc]">
        <States :value="s.pay[sc]">
          <template #idle>Subscribe</template>
          <template #busy><Spinner :size="14" /></template>
          <!-- The amount is the feedback while it leaves the button. Showing
               the success label underneath would put two messages in one place. -->
          <template #paid />
          <template #done>
            <span class="sb-done">
              <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M3.5 8.5 6.5 11.5 12.5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              Subscribed
            </span>
          </template>
        </States>
      </div>
    </section>

    <Fly v-if="s.fly" :from="s.fly.from" :to="s.fly.to" :go="s.fly.go" held :duration="900">
      <span class="sb-pill sb-pill--chip">+${{ SCENES[s.fly.scene].pulses[s.fly.i].price }}</span>
    </Fly>
  </Stage>
</template>
