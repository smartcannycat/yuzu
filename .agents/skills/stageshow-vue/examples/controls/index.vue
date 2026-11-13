<script setup lang="ts">
import {
  Badge,
  Bar,
  Camera,
  Chart,
  Code,
  Field,
  Segmented,
  Scroll,
  Slot as StageSlot,
  Stage,
  Tabs,
  Toggle,
  type Act,
  type Rect,
} from '../../kit'
import './controls.css'

const DATA = [12, 18, 15, 24, 22, 31, 28, 36]
const MORE = [12, 18, 15, 24, 22, 31, 34, 44]
const DIFF = [
  { text: 'function load(id) {' },
  { text: '  let r = fetch(id)', kind: 'del' as const },
  { text: '  let r = cache.get(id)', kind: 'add' as const },
  { text: '  return r.json()' },
  { text: '}' },
]
const ROWS = ['Acme', 'Globex', 'Initech', 'Umbrella', 'Hooli', 'Vandelay', 'Stark', 'Wayne']

type S = {
  email: string
  focus: boolean
  seg: number
  on: boolean
  tab: number
  lines: number
  data: number[]
  carry: { x: number; y: number; w: number; settle?: boolean } | null
  moved: boolean
  leaving: boolean
  focusTile: Rect | null
}

const initial: S = { email: '', focus: false, seg: 0, on: false, tab: 0, lines: 0, data: DATA, carry: null, moved: false, leaving: false, focusTile: null }
const POSTER: S = { ...initial, email: 'ada@acme.dev', seg: 1, on: true, tab: 1, lines: 5, data: MORE, moved: true }

async function script(a: Act<S>) {
  await a.wait(500)
  a.mark('field')
  await a.click('email')
  await a.set({ focus: true })
  await a.type('email', 'ada@acme.dev')
  await a.wait(300)

  a.mark('controls')
  await a.click({ at: 'seg-1', x: 0.84, y: 0.7 })
  await a.set({ seg: 1, focus: false })
  await a.click('toggle')
  await a.set({ on: true })
  await a.click('tab-1')
  await a.set({ tab: 1 })

  a.mark('code')
  a.move('rest')
  for (let i = 1; i <= DIFF.length; i++) {
    a.put({ lines: i })
    await a.wait(140)
  }
  await a.set({ data: MORE })
  await a.wait(600)

  a.mark('slot')
  const GRAB = { x: 0.72, y: 0.24 }
  await a.move({ at: 'card', ...GRAB })
  const card = a.rect('card')
  const col = a.rect('col-b')
  const end = { x: col.x + 6, y: col.y + 6 }
  const grab = { x: card.width * GRAB.x, y: card.height * GRAB.y }
  await a.drag({ x: end.x + grab.x, y: end.y + grab.y }, (at) => {
    a.put({ carry: { x: at.x - grab.x, y: at.y - grab.y, w: card.width } })
  })
  await a.set({ carry: { ...end, w: card.width, settle: true } })
  await a.wait(220)
  await a.set({ carry: null, moved: true })
  await a.wait(400)

  a.mark('scroll')
  await a.scroll('list', 'row-5')
  await a.wait(500)

  a.mark('camera')
  await a.move('rest')
  await a.set({ focusTile: a.rect(a.layout === 'compact' ? 'code-detail' : 't-code', { layout: true }) })
  await a.wait(2200)
  await a.set({ focusTile: null })
  await a.wait(1400)

  a.mark('exit')
  await a.scroll('list', 0)
  await a.set({ leaving: true })
  await a.wait(220)
  await a.set({ ...initial, data: DATA })
  await a.move('rest')
  await a.wait(900)
}
</script>

<template>
  <Stage
    :specimen="true"
    :width="760"
    :height="460"
    :compact="{ below: 600, width: 358, height: 1312 }"
    :initial="initial"
    :poster="POSTER"
    :script="script"
    :cursor="{ at: 'rest', style: 'arrow', ripple: true }"
    class="ct"
  >
    <template #default="{ state: s, layout }">
      <Camera :focus="s.focusTile" :pad="layout === 'compact' ? 24 : 32">
        <div class="ct-grid">
          <div class="ct-tile">
            <span class="ct-name">Field</span>
            <div class="ct-body">
              <Field
                label="Email"
                :value="s.email"
                placeholder="you@company.com"
                :focused="s.focus"
                :status="s.email.endsWith('.dev') ? 'valid' : undefined"
                :box="{ 'data-target': 'email' }"
                class="ct-field"
              />
            </div>
          </div>

          <div class="ct-tile">
            <span class="ct-name">Segmented, Toggle, Tabs</span>
            <div class="ct-body">
              <Segmented :items="['Monthly', 'Yearly']" :value="s.seg" :targets="['seg-0', 'seg-1']" />
              <div class="ct-switch">
                <span>Auto-renew</span>
                <Toggle :on="s.on" data-target="toggle" data-cursor="hand" />
              </div>
              <Tabs :items="['Overview', 'Usage', 'Billing']" :value="s.tab" :targets="['tab-0', 'tab-1', 'tab-2']" />
            </div>
          </div>

          <div class="ct-tile" data-target="t-code">
            <span class="ct-name">Code</span>
            <div class="ct-body">
              <div class="ct-code-focus" data-target="code-detail">
                <Code :lines="DIFF" :start="12" :count="s.lines" class="ct-code" />
              </div>
            </div>
          </div>

          <div class="ct-tile">
            <span class="ct-name">Chart</span>
            <div class="ct-body">
              <Chart :data="s.data" :width="190" :height="64" />
              <Chart :data="s.data" kind="bars" :width="190" :height="34" />
            </div>
          </div>

          <div class="ct-tile">
            <span class="ct-name">Slot</span>
            <div class="ct-body">
              <div class="ct-cols">
                <div class="ct-col">
                  <StageSlot :open="!s.moved && !s.carry" :height="50" :gap="6">
                    <div v-if="!s.moved && !s.carry" data-target="card" data-cursor="open" class="ct-fade-in">
                      <div class="ct-card">
                        <Bar w="72%" :h="6" :tone="4" />
                        <Badge tone="accent">Review</Badge>
                      </div>
                    </div>
                  </StageSlot>
                  <Bar w="100%" :h="50" :r="8" :tone="1" />
                </div>
                <div class="ct-col" data-target="col-b">
                  <StageSlot :open="!!s.carry || s.moved" :height="50" :gap="6" :dashed="!!s.carry" data-target="dropzone">
                    <div v-if="s.moved" class="ct-fade" :data-out="s.leaving || undefined">
                      <div class="ct-card">
                        <Bar w="72%" :h="6" :tone="4" />
                        <Badge tone="accent">Review</Badge>
                      </div>
                    </div>
                  </StageSlot>
                  <Bar w="100%" :h="50" :r="8" :tone="1" />
                </div>
              </div>
            </div>
          </div>

          <div class="ct-tile">
            <span class="ct-name">Scroll</span>
            <div class="ct-body">
              <Scroll name="list" class="ct-list">
                <div v-for="(r, i) in ROWS" :key="r" class="ct-row" :data-target="`row-${i}`">
                  <Bar :w="14" :h="14" :r="7" :tone="2" />
                  {{ r }}
                </div>
              </Scroll>
            </div>
          </div>
        </div>

        <div
          v-if="s.carry"
          class="ct-carry"
          :data-settle="s.carry.settle || undefined"
          :style="{ left: `${s.carry.x}px`, top: `${s.carry.y}px`, width: `${s.carry.w}px` }"
        >
          <div class="ct-card">
            <Bar w="72%" :h="6" :tone="4" />
            <Badge tone="accent">Review</Badge>
          </div>
        </div>
      </Camera>
      <span class="ct-rest" data-target="rest" />
    </template>
  </Stage>
</template>
