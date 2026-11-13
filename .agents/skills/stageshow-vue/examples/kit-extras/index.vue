<script setup lang="ts">
import { Avatar, BrandMark, Chip, Expand, Icon, Menu, Meter, Stage, Swap, type Act, type IconName, type Rect } from '../../kit'
import '../parts/parts.css'
import './extras.css'

// A second specimen sheet: Chip, Swap, Avatar rings, Meter tones, Menu
// hover, Expand, the solid glyphs and BrandMark. A catalog of how each
// behaves, not a composition to copy.

const LINES = ['Ship it on Friday.', 'Ship it on Friday, once QA has signed off on the release.']
const STRENGTH = [
  { v: 0.2, tone: 'danger' },
  { v: 0.5, tone: 'warning' },
  { v: 0.95, tone: 'success' },
] as const
const GLYPHS: IconName[] = ['lock', 'play', 'pause', 'heart', 'star', 'home', 'mail', 'bell', 'user', 'bolt']

type S = { chip: boolean; line: number; rings: number; strength: number; menu: boolean; open: boolean; card: Rect }
const REST = { wide: { x: 700, y: 430 }, compact: { x: 316, y: 1478 } }
const ZERO: Rect = { x: 0, y: 0, width: 0, height: 0 }
const initial: S = { chip: true, line: 0, rings: 0, strength: -1, menu: true, open: false, card: ZERO }
const POSTER: S = { ...initial, line: 1, rings: 2, strength: 2 }

async function script(a: Act<S>) {
  await a.set({ card: a.rect('card', { layout: true }) })
  await a.wait(600)
  a.mark('chip')
  await a.click('chip-x')
  await a.set({ chip: false })
  await a.wait(700)
  await a.set({ chip: true })
  a.mark('swap')
  await a.set({ line: 1 })
  await a.wait(900)
  a.mark('rings')
  await a.set({ rings: 1 })
  await a.wait(500)
  await a.set({ rings: 2 })
  a.mark('meter')
  for (const i of [0, 1, 2]) {
    await a.set({ strength: i })
    await a.wait(450)
  }
  a.mark('menu')
  for (const t of ['m0', 'm1', 'm2']) {
    await a.move(t)
    await a.wait(600)
  }
  a.mark('expand')
  await a.click('card')
  await a.set({ open: true })
  await a.wait(1400)
  await a.set({ open: false })
  await a.wait(800)
  await a.move(REST[a.layout])
  a.mark('exit')
  await a.set({ line: 0, rings: 0, strength: -1, card: ZERO })
  await a.wait(1000)
}
</script>

<template>
  <Stage
    specimen
    :width="760"
    :height="460"
    :compact="{ below: 600, width: 358, height: 1514 }"
    :initial="initial"
    :poster="POSTER"
    :script="script"
    :cursor="{ at: REST }"
    class="pt"
    v-slot="{ state: s }"
  >
    <div class="kx-grid">
      <div class="pt-tile">
        <span class="pt-name">Chip</span>
        <div class="pt-body">
          <div class="kx-chips">
            <Chip :show="s.chip" remove="chip-x" :gap="6">Pro</Chip>
            <Chip>Open</Chip>
          </div>
        </div>
      </div>

      <div class="pt-tile">
        <span class="pt-name">Swap</span>
        <div class="pt-body">
          <p class="kx-para">
            <Swap :id="s.line">{{ LINES[s.line] }}</Swap>
          </p>
        </div>
      </div>

      <div class="pt-tile">
        <span class="pt-name">Avatar ring</span>
        <div class="pt-body">
          <div class="kx-row">
            <Avatar name="Maya" :size="26" :ring="s.rings >= 1 ? 'confirmed' : 'waiting'" />
            <Avatar name="Jon" :size="26" :ring="s.rings >= 2 ? 'confirmed' : 'waiting'" />
            <Avatar name="Ana" :size="26" :ring="s.rings >= 2 ? 'declined' : 'waiting'" />
          </div>
        </div>
      </div>

      <div class="pt-tile">
        <span class="pt-name">Meter tone</span>
        <div class="pt-body">
          <Meter class="kx-meter" :value="s.strength < 0 ? 0 : STRENGTH[s.strength].v" :tone="s.strength < 0 ? 'danger' : STRENGTH[s.strength].tone" />
        </div>
      </div>

      <div class="pt-tile">
        <span class="pt-name">Menu hover</span>
        <div class="pt-body">
          <div class="kx-menu">
            <Menu :targets="['m0', 'm1', 'm2']" :items="['Rename', 'Duplicate', 'Move to…']" />
          </div>
        </div>
      </div>

      <div class="pt-tile kx-tall">
        <span class="pt-name">Expand</span>
        <div class="pt-body">
          <div class="kx-screen">
            <div class="kx-list">
              <div class="kx-card kx-card--ghost" />
              <div class="kx-card" data-target="card" data-cursor="hand" />
              <div class="kx-card kx-card--ghost" />
            </div>
            <Expand :open="s.open" :from="s.card" :radius="12" class="kx-expand">
              <div class="kx-art" />
              <div class="kx-detail">
                <span class="kx-bar" :style="{ width: '60%' }" />
                <span class="kx-bar" :style="{ width: '85%' }" />
                <span class="kx-bar" :style="{ width: '70%' }" />
              </div>
            </Expand>
          </div>
        </div>
      </div>

      <div class="pt-tile kx-wide">
        <span class="pt-name">Icon filled</span>
        <div class="pt-body">
          <div class="kx-glyphs">
            <Icon v-for="g in GLYPHS" :key="g" :name="g" filled :size="16" />
          </div>
        </div>
      </div>

      <div class="pt-tile">
        <span class="pt-name">BrandMark</span>
        <div class="pt-body">
          <div class="kx-row">
            <BrandMark brand="slack" />
            <BrandMark brand="notion" />
            <BrandMark brand="linear" />
          </div>
        </div>
      </div>
    </div>
  </Stage>
</template>
