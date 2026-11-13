<script setup lang="ts">
import { Avatar, Bar, Facepile, Row, Stage, Text, Window, type Act } from '../../kit'
import './chip.css'

// A satellite chip pinned to a corner: a support inbox with "3 agents
// online" hanging off its top-right corner. Beats: the chip rises into its
// corner after the window has settled. Plays once; the still is the payoff.
//
// What makes a corner chip read as pinned, not floating:
// - Its center sits on the window's corner, or within a few px of it: about
//   half outside, half over the chrome. Over the window's middle it covers
//   content; well clear of the corner it floats off.
// - It sits over chrome or filler only, never over the window's words.
// - It is small and says one thing, with one visual (the agents' faces), on
//   a raised surface a level above the window.
// - The window is pinned top-left and runs off the bottom; the chip's corner
//   keeps a gutter to the stage's right edge so the chip is whole.
//
// Real strings: the chip, the inbox title and the top conversation.

type S = { on: boolean }

async function script(a: Act<S>) {
  await a.wait(600)
  a.put({ on: true })
  await a.wait(2600)
}
</script>

<template>
  <Stage
    :width="520"
    :height="360"
    :compact="{ below: 520, width: 358, height: 360 }"
    :initial="{ on: false }"
    :poster="{ on: true }"
    :script="script"
    play="once"
    class="cc"
    v-slot="{ state: s }"
  >
    <Window title="Support" class="cc-win">
      <div class="cc-list">
        <Row selected>
          <template #lead><Avatar name="Priya Nair" :size="28" /></template>
          <template #title><Text>Priya Nair</Text></template>
          <template #meta><Text>2m</Text></template>
          <template #subtitle><Text>Can I move my plan to annual billing?</Text></template>
        </Row>
        <Row v-for="(w, i) in [180, 150, 200, 140]" :key="i">
          <template #lead><Avatar :size="28" /></template>
          <template #title><Bar :w="80" :h="7" :r="3.5" :tone="3" /></template>
          <template #meta><Bar :w="20" :h="6" :r="3" :tone="2" /></template>
          <template #subtitle><Bar :w="w" :h="6" :r="3" :tone="2" /></template>
        </Row>
      </div>
    </Window>
    <div class="cc-chip" :data-on="s.on || undefined">
      <Facepile :names="['Ana Ruiz', 'Jon Park', 'Leo Sato']" :size="20" :overlap="3" />
      <Text class="cc-chip__text">3 agents online</Text>
    </div>
  </Stage>
</template>
