<script setup lang="ts">
import { RotateCw } from 'lucide-vue-next'
import { Avatar, Badge, Bar, Stage, Window, type Act } from '../../kit'
import './loading.css'

// Loading to content: a list of orders arrives into its own skeleton. Beats:
// the skeleton holds a moment, the rows resolve top to bottom, the list
// holds; then Refresh is pressed, the rows dim back to the skeleton and
// resolve again. Loops; the reset is the refresh.
//
// What makes a skeleton resolve without a jolt:
// - The skeleton is the content's own geometry. Each bar sits in the same
//   grid cell as the words it stands for, at the words' x-height and about
//   their width, so nothing moves when they arrive: the bar fades as its
//   words fade in, in place.
// - Only the data loads. The window, the title and the column heads are
//   real from the first frame; a skeleton over the chrome reads as a page
//   that hasn't loaded at all.
// - Rows resolve top to bottom, 70ms apart, each whole (avatar, name,
//   amount and status together), so the eye reads down the list once.
// - The shimmer is faint and slow, and it stops the moment a row resolves.
//
// Four rows, the window running off just under the last: the stage may only
// cut the window's empty foot, never a row's words.
//
// Real strings: the title, the column heads, every resolved row.

type S = { ready: boolean; spin: number }

const ROWS = [
  { who: 'Maya Chen', what: 'Pro, annual', amount: '$588.00', status: 'Paid' },
  { who: 'Jon Park', what: 'Team, monthly', amount: '$99.00', status: 'Paid' },
  { who: 'Ana Ruiz', what: 'Pro, monthly', amount: '$49.00', status: 'Refunded' },
  { who: 'Leo Sato', what: 'Team, annual', amount: '$1,188.00', status: 'Paid' },
]
// Each bar about its words' width
const W = [[74, 70], [60, 82], [64, 74], [58, 76]]
const AW = [52, 44, 40, 60]
const BW = [42, 42, 62, 42]

async function script(a: Act<S>) {
  await a.wait(1100)
  a.mark('resolve')
  a.put({ ready: true })
  await a.wait(2600)
  a.mark('refresh')
  await a.move('refresh')
  await a.wait(150)
  await a.click('refresh')
  a.put({ ready: false, spin: 1 })
  await a.wait(1000)
  a.put({ spin: 0 })
  await a.move({ at: 'refresh', x: 3, y: 6 }, { duration: 700 })
}
</script>

<template>
  <Stage
    :width="600"
    :height="400"
    :compact="{ below: 600, width: 358, height: 400 }"
    :initial="{ ready: false, spin: 0 }"
    :poster="{ ready: true, spin: 0 }"
    :script="script"
    :cursor="{ at: { x: 520, y: 370 } }"
    class="ld"
    v-slot="{ state: s }"
  >
    <Window url="dashboard.tally.com/orders" class="ld-win">
      <div class="ld-body">
        <header class="ld-head">
          <div class="ld-title">Recent orders</div>
          <span class="ld-refresh" data-target="refresh" data-cursor="hand" :data-spin="s.spin || undefined">
            <RotateCw :size="14" :stroke-width="2" />
          </span>
        </header>
        <div class="ld-row ld-row--cols">
          <span>Customer</span>
          <span class="ld-num">Amount</span>
          <span>Status</span>
        </div>
        <div
          v-for="(r, i) in ROWS"
          :key="r.who"
          class="ld-row"
          :data-ready="s.ready || undefined"
          :style="{ '--i': i }"
        >
          <span class="ld-who">
            <span class="ld-slot ld-slot--av">
              <Bar :w="28" :h="28" :r="14" :tone="2" class="ld-sk" />
              <Avatar :name="r.who" :size="28" class="ld-real" />
            </span>
            <span class="ld-lines">
              <span class="ld-slot">
                <Bar :w="W[i]![0]!" :h="8" :r="4" :tone="2" class="ld-sk" />
                <span class="ld-real ld-name">{{ r.who }}</span>
              </span>
              <span class="ld-slot">
                <Bar :w="W[i]![1]!" :h="7" :r="3.5" :tone="2" class="ld-sk" />
                <span class="ld-real ld-what">{{ r.what }}</span>
              </span>
            </span>
          </span>
          <span class="ld-slot ld-num">
            <Bar :w="AW[i]!" :h="8" :r="4" :tone="2" class="ld-sk" />
            <span class="ld-real">{{ r.amount }}</span>
          </span>
          <span class="ld-slot">
            <Bar :w="BW[i]!" :h="20" :r="10" :tone="2" class="ld-sk" />
            <span class="ld-real">
              <Badge :tone="r.status === 'Paid' ? 'success' : 'neutral'">{{ r.status }}</Badge>
            </span>
          </span>
        </div>
      </div>
    </Window>
  </Stage>
</template>
