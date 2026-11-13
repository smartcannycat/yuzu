<script setup lang="ts">
import { Chart, Icon, Meter, Stage, Text, type Act } from '../../kit'
import './stacked.css'

// Stacked cards: a plan card over the usage chart it bills from, two
// components of one product at one width. Beats: the usage bar fills, then
// the chart's bars grow under it. Plays once; the still is the payoff.
//
// What makes a stack read as one object:
// - One width, one left edge, a small gap (12px). Different widths or a
//   stagger turns it into two things that happen to be near each other.
// - The top card is whole; the bottom one runs off the stage's bottom edge
//   (the chart's axis is filler). Nothing else is cut.
// - Centered on the stage with even gutters; the ground does nothing.
// - The two cards share one number: the meter's 4.2M of 5M is the chart's
//   total, so they read as cause and detail.
//
// Real strings: the plan, its price, the usage line, the chart's title.

type S = { on: boolean }

const BARS = [8, 12, 9, 15, 13, 18, 11, 17, 22, 16, 20, 26, 21, 29, 24, 31, 27, 34]

async function script(a: Act<S>) {
  await a.wait(500)
  a.put({ on: true })
  await a.wait(3000)
}
</script>

<template>
  <Stage
    :width="520"
    :height="400"
    :compact="{ below: 520, width: 358, height: 400 }"
    :initial="{ on: false }"
    :poster="{ on: true }"
    :script="script"
    play="once"
    class="sk"
    v-slot="{ state: s, layout }"
  >
    <div class="sk-stack">
      <section class="sk-card">
        <div class="sk-plan">
          <span class="sk-mark"><Icon name="bolt" :size="14" /></span>
          <div class="sk-who">
            <Text class="sk-name">Pro plan</Text>
            <Text class="sk-sub">$49 per month</Text>
          </div>
        </div>
        <div class="sk-usage">
          <Text class="sk-label">API calls</Text>
          <Text class="sk-value">4.2M of 5M</Text>
        </div>
        <Meter :value="s.on ? 0.84 : 0" />
      </section>
      <section class="sk-card">
        <Text class="sk-label">Calls, last 18 days</Text>
        <Chart kind="bars" class="sk-chart" :data="BARS" :width="layout === 'compact' ? 286 : 300" :height="140" :show="s.on" />
      </section>
    </div>
  </Stage>
</template>
