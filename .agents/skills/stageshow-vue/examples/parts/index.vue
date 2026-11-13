<script setup lang="ts">
import { Bar, Check, Connector, Icon, LockScreen, Menu, Meter, Notification, Phone, WALLPAPER, Popover, Spinner, Stage, States, Stream, type Act } from '../../kit'
import { testFlight } from '../../assets/app-icons'
import './parts.css'

// A specimen sheet for the kit's newer parts, one tile each, playing in turn.
// It is a catalog, not a composition: for framing, copy the gold examples
// (hero-demo, static-card, story, payout-flow), not this layout.

const REWRITE = 'Ship faster with a preview for every branch.'
const CHANGED = new Set([3, 4, 5])

type S = {
  button: 'idle' | 'busy' | 'done'
  check: 'idle' | 'pending' | 'done'
  meter: number
  words: number
  marks: boolean
  steps: number
  menu: boolean
  item: number
  note: boolean
}

const initial: S = { button: 'idle', check: 'idle', meter: 0.25, words: 0, marks: false, steps: 0, menu: false, item: -1, note: false }
const POSTER: S = { button: 'done', check: 'done', meter: 0.8, words: 99, marks: true, steps: 2, menu: true, item: 1, note: true }

async function script(a: Act<S>) {
  await a.wait(600)
  a.mark('states')
  await a.click('deploy')
  await a.set({ button: 'busy', check: 'pending' })
  await a.wait(1300)
  await a.set({ button: 'done', check: 'done', meter: 0.8 })
  await a.wait(500)

  a.mark('stream')
  a.move('rest')
  for (let i = 1; i <= REWRITE.split(' ').length; i++) {
    a.put({ words: i })
    await a.wait(90)
  }
  await a.wait(300)
  await a.set({ marks: true })
  await a.wait(400)

  a.mark('connector')
  await a.set({ steps: 1 })
  await a.wait(1000)
  await a.set({ steps: 2 })
  await a.wait(500)

  a.mark('menu')
  await a.click('row', { right: true })
  await a.set({ menu: true })
  await a.wait(350)
  for (const i of [0, 1, 2]) {
    a.put({ item: i })
    await a.wait(280)
  }
  await a.click()
  await a.set({ menu: false, note: true })
  a.move('rest')
  await a.wait(2600)

  a.mark('exit')
  await a.set(initial)
  await a.wait(1000)
}
</script>

<template>
  <Stage
    specimen
    :width="760"
    :height="460"
    :compact="{ below: 600, width: 358, height: 1532 }"
    :initial="initial"
    :poster="POSTER"
    :script="script"
    :cursor="{ at: 'rest' }"
    class="pt"
    v-slot="{ state: s, rect, layout }"
  >
    <div class="pt-grid">
      <div class="pt-tile pt-a">
        <span class="pt-name">States</span>
        <div class="pt-body">
          <span class="pt-button" data-target="deploy" data-cursor="hand" :data-state="s.button">
            <States :value="s.button">
              <template #idle>Deploy</template>
              <template #busy>
                <Spinner :size="13" />
                Deploying
              </template>
              <template #done>
                <Icon name="check" :size="13" :stroke="2" />
                Deployed
              </template>
            </States>
          </span>
        </div>
      </div>

      <div class="pt-tile pt-b">
        <span class="pt-name">Check, Meter</span>
        <div class="pt-body">
          <div class="pt-status">
            <Check :on="s.check === 'done'" :pending="s.check === 'pending'" :size="18" />
            <span>storefront</span>
          </div>
          <Meter :value="s.meter" class="pt-meter" />
        </div>
      </div>

      <div class="pt-tile pt-c">
        <span class="pt-name">Stream</span>
        <div class="pt-body">
          <p class="pt-copy">
            <Stream :text="REWRITE" :count="s.words" :mark="(_, i) => s.marks && CHANGED.has(i)" />
          </p>
          <span class="pt-rest" data-target="rest" />
        </div>
      </div>

      <div class="pt-tile pt-d">
        <span class="pt-name">Connector</span>
        <div class="pt-body">
          <div class="pt-ends">
            <span class="pt-end" data-target="srv">
              <Bar :w="34" :h="6" :tone="4" />
            </span>
            <span class="pt-end" data-target="ep">
              <Bar :w="34" :h="6" :tone="4" />
            </span>
          </div>
        </div>
      </div>

      <div class="pt-tile pt-e">
        <span class="pt-name">Popover, Menu</span>
        <div class="pt-body">
          <div class="pt-rows">
            <div
              v-for="i in [0, 1, 2]"
              :key="i"
              class="pt-row"
              :data-target="i === 0 ? 'row' : undefined"
              :data-on="(i === 0 && s.menu) || undefined"
            >
              <Bar :w="14" :h="14" :r="4" :tone="2" />
              <Bar :w="[120, 90, 104][i]" :h="6" />
            </div>
          </div>
        </div>
      </div>

      <div class="pt-tile pt-f">
        <span class="pt-name">LockScreen satellite</span>
        <div class="pt-body">
          <Phone :width="layout === 'compact' ? 280 : 150" dark :wallpaper="WALLPAPER">
            <LockScreen size="satellite" stack="top">
              <Notification
                :data-show="s.note || undefined"
                class="pt-note"
                title="Promoted"
                body="storefront is live with this build."
              >
                <template #icon>
                  <img :src="testFlight" alt="" />
                </template>
              </Notification>
            </LockScreen>
          </Phone>
        </div>
      </div>
    </div>

    <Connector
      :from="{ x: rect('srv').x + rect('srv').width, y: rect('srv').y + rect('srv').height / 2 - 6 }"
      :to="{ x: rect('ep').x, y: rect('srv').y + rect('srv').height / 2 - 6 }"
      route="straight"
      :show="s.steps >= 1"
      arrow
    />
    <Connector
      :from="{ x: rect('ep').x, y: rect('srv').y + rect('srv').height / 2 + 6 }"
      :to="{ x: rect('srv').x + rect('srv').width, y: rect('srv').y + rect('srv').height / 2 + 6 }"
      route="straight"
      :show="s.steps >= 2"
      arrow
      dashed
    />

    <Popover
      :show="s.menu"
      class="pt-menu"
      :style="{ left: `${rect('row').x + 64}px`, top: `${rect('row').y + rect('row').height + 4}px` }"
    >
      <Menu :items="['Redeploy', 'Copy URL', 'Promote']" :value="s.item" />
    </Popover>
  </Stage>
</template>
