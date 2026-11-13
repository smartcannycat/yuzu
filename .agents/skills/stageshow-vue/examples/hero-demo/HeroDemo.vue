<script setup lang="ts">
import { Bar, Stage, Text, Window, between, contains, inset, type Act, type Point, type Rect, States } from '../../kit'
import Icon from './icons.vue'
import './hero.css'

// A dev tool's hero: annotate a dashboard three ways, copy the feedback,
// paste it into Claude Code.

type Tone = 'blue' | 'green' | 'orange'
type Marker = { at: Point; show: boolean }

type S = {
  toolbar: boolean
  highlight: boolean
  popup: { show: boolean; header: string; at: Point; tone: Tone }
  typed: string
  drag: Rect | null
  /** The marquee shows while the drag runs, and fades on release */
  dragging: boolean
  area: { r: Rect; show: boolean }
  picked: string[]
  selection: Rect | null
  m3: Marker
  m4: Marker
  m5: Marker
  copied: boolean
  terminal: boolean
  pasted: string
}

const hidden = (m: Marker): Marker => ({ ...m, show: false })

const initial: S = {
  toolbar: false,
  highlight: false,
  popup: { show: false, header: '', at: { x: 0, y: 0 }, tone: 'blue' },
  typed: '',
  drag: null,
  dragging: false,
  area: { r: { x: 0, y: 0, width: 0, height: 0 }, show: false },
  picked: [],
  selection: null,
  m3: { at: { x: 0, y: 0 }, show: false },
  m4: { at: { x: 0, y: 0 }, show: false },
  m5: { at: { x: 0, y: 0 }, show: false },
  copied: false,
  terminal: false,
  pasted: '',
}

const TITLE = "Maya's Dashboard"
const OUTPUT = `## Page feedback

Export button: primary style
Sidebar icons: hover states
Dashboard title: more prominence`

const REST = { wide: { x: 432, y: 212 }, compact: { x: 280, y: 270 } }
const POSTER: S = { ...initial, toolbar: true, copied: true, terminal: true, pasted: OUTPUT }

const pxBox = (r: Rect) => ({
  left: `${r.x}px`,
  top: `${r.y}px`,
  width: `${r.width}px`,
  height: `${r.height}px`,
})

async function annotate(a: Act<S>, header: string, tone: Tone, at: Point, text: string) {
  const width = a.layout === 'compact' ? 358 : 720
  const placed = { x: Math.max(116, Math.min(width - 116, at.x)), y: at.y }
  await a.set((s) => ({ popup: { ...s.popup, show: true, header, at: placed, tone }, typed: '' }))
  await a.wait(300)
  await a.type('typed', text)
  await a.wait(300)
  await a.click('add')
  await a.set((s) => ({ popup: { ...s.popup, show: false } }))
  await a.wait(200)
}

async function script(a: Act<S>) {
  await a.wait(600)

  // Open the toolbar
  await a.move('toolbar')
  await a.wait(300)
  await a.click()
  await a.set({ toolbar: true })
  await a.wait(400)
  await a.wait(200)

  // 1. Click an element
  await a.move('export')
  await a.set({ highlight: true })
  await a.wait(400)
  await a.click()
  await a.set({ highlight: false })
  await a.wait(100)
  const btn = a.rect('export')
  await annotate(a, 'button.export-btn', 'blue', { x: btn.x + btn.width / 2 - 80, y: btn.y + btn.height + 10 }, 'Change to primary style')
  await a.set({ m3: { at: a.center('export'), show: true } })
  await a.wait(600)

  // 2. Drag over an area
  const icons = a.rect('icons')
  const from = { x: icons.x + icons.width + 2, y: icons.y + icons.height + 2 }
  const to = { x: icons.x - 2, y: icons.y - 2 }
  await a.move(from)
  await a.wait(150)
  await a.drag(to, (at) => {
    const drag = between(from, at)
    const picked = ['icon-0', 'icon-1', 'icon-2'].filter((n) => contains(drag, a.rect(n)))
    a.put({ drag, picked, dragging: true })
  })
  await a.wait(200)
  await a.set({ dragging: false, picked: [], area: { r: between(from, to), show: true } })
  await annotate(a, 'Sidebar icons', 'green', { x: to.x + 110, y: (from.y + to.y) / 2 - 40 }, 'Add hover states')
  await a.set({ m4: { at: { x: from.x, y: to.y }, show: true } })
  await a.wait(400)

  // 3. Select text
  const title = a.rect('title')
  const y = title.y + title.height / 2
  await a.move({ x: title.x, y })
  await a.wait(150)
  await a.drag({ x: title.x + title.width, y }, (at) =>
    a.put({ selection: { x: title.x, y: title.y - 2, width: at.x - title.x, height: 16 } }),
  )
  await a.wait(200)
  await annotate(a, `"${TITLE}"`, 'orange', { x: Math.max(100, title.x + title.width / 2), y: title.y + title.height + 7 }, 'Make this more prominent')
  await a.set({ selection: null, m5: { at: { x: title.x + title.width + 2, y }, show: true } })
  await a.wait(400)

  // Copy, then paste into the agent
  await a.move('copy')
  await a.wait(400)
  await a.click()
  await a.set({ copied: true })
  await a.wait(400)
  await a.set({ terminal: true })
  await a.wait(600)
  await a.click('terminal-input')
  await a.key('cmd+v')
  await a.set({ pasted: OUTPUT })
  await a.move('rest')
  await a.wait(2000)

  // Put everything back, so the loop has no seam
  await a.set((s) => ({ ...initial, m3: hidden(s.m3), m4: hidden(s.m4), m5: hidden(s.m5), area: { ...s.area, show: false }, pasted: s.pasted, popup: s.popup }))
  await a.move('rest')
  await a.wait(400)
  await a.set({ ...initial })
}

const mono = 'ui-monospace, SFMono-Regular, monospace'

const METRICS: [number, number][] = [
  [45, 50],
  [55, 65],
  [38, 40],
]

const TABLE_ROWS: [string | number, string | number, number][] = [
  ['api-gateway', 'main', 48],
  ['web', 'release-1.4', 42],
  [62, 38, 48],
]
</script>

<template>
  <Stage
    :width="720"
    :height="340"
    :compact="{ below: 600, width: 358, height: 400 }"
    :initial="initial"
    :poster="POSTER"
    :script="script"
    :cursor="{ at: REST }"
    class="hd"
    v-slot="{ state: s, rect, layout }"
  >
    <Window url="localhost:3000" class="hd-browser" :data-cursor="s.toolbar ? 'crosshair' : 'pointer'" :receded="s.terminal">
      <div class="hd-content">
        <aside class="hd-sidebar">
          <Bar class="hd-sidebar-logo" :w="20" :h="20" :r="5" :tone="4" />
          <div class="hd-sidebar-icons" data-target="icons">
            <Bar
              v-for="i in [0, 1, 2]"
              :key="i"
              :data-target="`icon-${i}`"
              class="hd-sidebar-icon"
              :w="16"
              :h="16"
              :r="4"
              :tone="i === 1 ? 5 : 3"
              :data-selected="s.picked.includes(`icon-${i}`)"
            />
          </div>
          <div class="hd-sidebar-bottom">
            <Bar :w="16" :h="16" :r="8" :tone="3" />
          </div>
        </aside>

        <main class="hd-main">
          <div class="hd-header">
            <div class="hd-header-left">
              <span class="hd-logo" />
              <span class="hd-title" data-target="title" data-cursor="ibeam">
                {{ TITLE }}
              </span>
            </div>
            <Bar data-target="export" :w="55" :h="26" :r="5" :tone="3" />
          </div>

          <div class="hd-metrics">
            <div v-for="([label, value], i) in METRICS" :key="i" class="hd-card" :data-target="`metric-${i}`">
              <Bar :w="label" :h="5" :tone="3" :style="{ marginBottom: '8px' }" />
              <Bar :w="value" :h="18" :r="3" :tone="4" />
            </div>
          </div>

          <div class="hd-table" data-crop>
            <div class="hd-row head">
              <Bar :w="60" :tone="4" />
              <Bar :w="45" :tone="4" />
              <Bar :w="40" :tone="4" />
            </div>
            <!-- Two real rows, one placeholder: a table, not a wireframe -->
            <div v-for="([a, b, pill], i) in TABLE_ROWS" :key="i" class="hd-row" :data-target="`row-${i}`">
              <Text v-if="typeof a === 'string'" class="hd-cell">{{ a }}</Text>
              <Bar v-else :w="a" :h="7" :tone="2" />
              <Text v-if="typeof b === 'string'" class="hd-cell hd-cell--faint">{{ b }}</Text>
              <Bar v-else :w="b" :h="7" :tone="2" />
              <Bar :w="pill" :h="18" :r="9" :tone="1" />
            </div>
          </div>

          <div class="hd-toolbar" data-target="toolbar" data-cursor="hand" :data-open="s.toolbar">
            <div class="hd-toolbar-icon">
              <Icon name="list-sparkle" :size="20" />
            </div>
            <div class="hd-toolbar-buttons">
              <div class="hd-toolbar-btn">
                <Icon name="pause" />
              </div>
              <div class="hd-toolbar-btn">
                <Icon name="eye" />
              </div>
              <div class="hd-toolbar-btn" data-target="copy" data-cursor="hand" :data-active="s.copied">
                <States :value="s.copied ? 'check' : 'copy'">
                  <template #copy><Icon name="copy" /></template>
                  <template #check><Icon name="check" /></template>
                </States>
              </div>
              <div class="hd-toolbar-btn">
                <Icon name="trash" />
              </div>
              <div class="hd-toolbar-btn">
                <Icon name="gear" />
              </div>
              <div class="hd-toolbar-divider" />
              <div class="hd-toolbar-btn">
                <Icon name="x" />
              </div>
            </div>
          </div>
        </main>
      </div>
    </Window>

    <!-- Overlays, positioned from measured targets -->
    <div class="hd-highlight" :data-show="s.highlight" :style="pxBox(inset(rect('export'), 4))" />
    <div class="hd-dragbox" :data-show="s.dragging || undefined" :style="s.drag ? pxBox(s.drag) : undefined" />
    <div class="hd-area" :data-show="s.area.show" :style="pxBox(s.area.r)" />
    <div
      v-if="s.selection"
      class="hd-selection"
      :style="{ left: `${s.selection.x}px`, top: `${s.selection.y}px`, width: `${s.selection.width}px` }"
    />

    <div class="hd-marker" data-show :style="{ left: `${rect('metric-0').x + 28}px`, top: `${rect('metric-0').y + 14}px` }">
      1
    </div>
    <div class="hd-marker" data-show :style="{ left: `${rect('row-0').x + 140}px`, top: `${rect('row-0').y + 10}px` }">
      2
    </div>
    <div class="hd-marker" :data-show="s.m3.show" :style="{ left: `${s.m3.at.x}px`, top: `${s.m3.at.y}px` }">
      3
    </div>
    <div class="hd-marker" data-tone="green" :data-show="s.m4.show" :style="{ left: `${s.m4.at.x}px`, top: `${s.m4.at.y}px` }">
      4
    </div>
    <div class="hd-marker" data-tone="orange" :data-show="s.m5.show" :style="{ left: `${s.m5.at.x}px`, top: `${s.m5.at.y}px` }">
      5
    </div>

    <div class="hd-popup" :data-show="s.popup.show" :data-tone="s.popup.tone" :style="{ left: `${s.popup.at.x}px`, top: `${s.popup.at.y}px` }">
      <div class="hd-popup-header">{{ s.popup.header }}</div>
      <div class="hd-popup-input" data-cursor="ibeam">
        {{ s.typed }}
        <span class="hd-caret" :style="{ opacity: 0.4 }">|</span>
      </div>
      <div class="hd-popup-actions">
        <div class="hd-popup-btn">Cancel</div>
        <div class="hd-popup-btn submit" data-target="add" data-cursor="hand">Add</div>
      </div>
    </div>

    <Window title="Maya's Project" class="hd-terminal" :data-show="s.terminal">
      <!-- A paste arrives as one operation after its keystroke. -->
      <div class="hd-terminal-body" data-target="terminal-input" data-cursor="ibeam" data-snap>
        <div class="hd-terminal-welcome">
          <svg viewBox="0 0 240 76" fill="none" :style="{ width: '100%', height: 'auto', display: 'block' }">
            <rect x="4" y="4" width="148" height="68" rx="3" stroke="#D97757" stroke-width="1.5" fill="none" />
            <text x="160" y="16" fill="rgba(0,0,0,0.7)" font-size="9" :font-family="mono" font-weight="500">
              Claude Code
            </text>
            <text x="160" y="26" fill="rgba(0,0,0,0.4)" font-size="7" :font-family="mono">
              v2.1.14
            </text>
            <text x="78" y="20" fill="rgba(0,0,0,0.6)" font-size="8" :font-family="mono" text-anchor="middle">
              Welcome back Maya!
            </text>
            <g transform="translate(56, 26) scale(0.35)">
              <path d="M104.998 0H20.998V16.2H104.998V0Z" fill="#D77757" />
              <path d="M34.998 16.1953H20.998V32.3953H34.998V16.1953Z" fill="#D77757" />
              <rect x="35" y="14.7266" width="56" height="29.4545" fill="black" />
              <path d="M84 14.7266H42V36.8175H84V14.7266Z" fill="#D77757" />
              <path d="M105.002 16.1953H91.002V32.3953H105.002V16.1953Z" fill="#D77757" />
              <path d="M119 32.4023H7V48.6023H119V32.4023Z" fill="#D77757" />
              <path d="M104.998 48.5977H20.998V64.7977H104.998V48.5977Z" fill="#D77757" />
              <path d="M35 64.8047H28V81.0047H35V64.8047Z" fill="#D77757" />
              <path d="M49 64.8047H42V81.0047H49V64.8047Z" fill="#D77757" />
              <path d="M84 64.8047H77V81.0047H84V64.8047Z" fill="#D77757" />
              <path d="M98.002 64.8047H91.002V81.0047H98.002V64.8047Z" fill="#D77757" />
            </g>
            <text x="78" y="62" fill="rgba(0,0,0,0.4)" font-size="7" :font-family="mono" text-anchor="middle">
              Opus 5.5 · ~/code/dashboard
            </text>
          </svg>
        </div>
        {{ s.pasted }}
        <span :style="{ opacity: 0.4 }">█</span>
      </div>
    </Window>
    <span data-target="rest" :style="{ position: 'absolute', left: `${REST[layout].x}px`, top: `${REST[layout].y}px` }" />
  </Stage>
</template>
