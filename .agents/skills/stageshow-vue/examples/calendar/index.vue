<script setup lang="ts">
import { Stage, Window, Bar, Avatar, Icon, Roll, Camera, cellOf, type Act, type Point, type Rect } from '../../kit'
import './calendar.css'

// Calendar hero, a week view with no sidebar so four days fit the column
// whole and Friday runs off the right: a meeting is dragged from Tuesday afternoon to Wednesday
// morning; once it lands, each attendee's availability is checked and their
// avatar turns green. Cmd+Z puts it back, a caused reset, and the loop begins
// again from the same frame.

const COLS = 5
const ROWS = 7
const COL_W = 108
const ROW_H = 40
const SPAN = 2
const GRIP = { x: 0.76, y: 0.28 }
const START = { col: 1, row: 4 } // Tue 1 PM
const END = { col: 2, row: 1 } // Wed 10 AM

type Cell = { col: number; row: number }
type Avail = 'idle' | 'pending' | 'ok'
// `at` is the carried card's top-left in grid pixels
type S = { cell: Cell; lifted: boolean; at: Point | null; target: Cell | null; avail: Avail[]; focus: Rect | null }

const DAYS = ['Mon 19', 'Tue 20', 'Wed 21', 'Thu 22', 'Fri 23']
const HOURS = ['9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM', '3 PM']
const PEOPLE = ['Maya', 'Jonah', 'Priya']
// [col, row, rows, bar width]
const BUSY: [number, number, number, number][] = [
  [0, 0, 1, 46],
  [0, 3, 2, 58],
  [1, 1, 1, 40],
  [2, 4, 1, 52],
  [3, 0, 2, 62],
  [3, 4, 1, 44],
  [4, 2, 1, 50],
]

const hour = (row: number) => 9 + row
const label = (h: number) => `${h > 12 ? h - 12 : h} ${h >= 12 ? 'PM' : 'AM'}`
const span = (c: Cell) => {
  const a = hour(c.row)
  const b = a + SPAN
  return a < 12 === b < 12 ? `${label(a).split(' ')[0]} – ${label(b)}` : `${label(a)} – ${label(b)}`
}

// A cell in grid pixels; offset by the grid's rect for stage pixels
const cellRect = (grid: { x: number; y: number }, c: Cell): Rect => ({
  x: grid.x + c.col * COL_W + 3,
  y: grid.y + c.row * ROW_H + 2,
  width: COL_W - 6,
  height: SPAN * ROW_H - 4,
})

const idle: Avail[] = ['idle', 'idle', 'idle']

// Compact starts the week at Tuesday, so the two days the story uses are
// whole at the phone's width: cells stay in whole-week columns in state, and
// are drawn `o` columns to the left
const shift = (c: Cell, o: number): Cell => ({ ...c, col: c.col - o })

async function carry(a: Act<S>, from: Cell, to: Cell, o: number) {
  const grid = a.rect('grid', { layout: true })
  const card = cellRect(grid, shift(from, o))
  // Hold the upper body of the meeting, leaving its attendee row clear.
  const grab = { x: card.x + card.width * GRIP.x, y: card.y + card.height * GRIP.y }
  await a.move(grab)
  await a.wait(150)
  const dest = cellRect(grid, shift(to, o))
  let prev: Cell = from
  await a.drag(
    { x: dest.x + (grab.x - card.x), y: dest.y + (grab.y - card.y) },
    (p) => {
      const at = { x: p.x - (grab.x - card.x), y: p.y - (grab.y - card.y) }
      // The card's top-center decides the cell, with sticky borders
      const col = cellOf(at.x + card.width / 2 - grid.x, COL_W, prev.col - o) + o
      const row = cellOf(at.y + ROW_H / 2 - grid.y, ROW_H, prev.row)
      prev = { col: Math.max(o, Math.min(COLS - 1, col)), row: Math.max(0, Math.min(ROWS - SPAN, row)) }
      // Lift only once drag has pressed and closed the hand. The callback
      // paints the card and cursor together from the first movement frame.
      a.put({ lifted: true, at: { x: at.x - grid.x, y: at.y - grid.y }, target: prev })
    },
    { duration: 1300 },
  )
  await a.set({ lifted: false, at: null, target: null, cell: prev })
}

const script = async (a: Act<S>) => {
  await a.wait(700)
  a.mark('drag')
  // Match the rendered week: compact starts at Tuesday, wide starts at Monday.
  const o = a.layout === 'compact' ? 1 : 0
  await carry(a, START, END, o)
  // Step the pointer off the card so the avatars are in clear view
  await a.move('aside')
  await a.wait(150)
  a.mark('check')
  // Push in on the meeting while its attendees are checked (wide only: the
  // compact crop is already close). The view keeps the month title in.
  const grid = a.rect('grid', { layout: true })
  const card = cellRect(grid, shift(END, o))
  const wide = o === 0
  if (wide) a.set({ focus: { x: card.x + card.width / 2 - 243, y: 20, width: 486, height: 267 } })
  await a.wait(wide ? 500 : 150)
  await a.stagger([0, 1, 2], (i) => a.set((s) => ({ avail: s.avail.map((v, j) => (j === i ? 'pending' : v)) })), 70)
  await a.wait(650)
  await a.stagger([0, 1, 2], (i) => a.set((s) => ({ avail: s.avail.map((v, j) => (j === i ? 'ok' : v)) })), 420)
  await a.wait(2000)
  await a.set({ focus: null })
  await a.wait(1100)
  // Undo: the meeting goes back and its availability is unknown again
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ cell: START, avail: idle })
  await a.wait(900)
  await a.move('rest')
  await a.wait(500)
}

function sceneGeo(s: S, layout: string) {
  const compact = layout === 'compact'
  const o = compact ? 1 : 0
  const origin = { x: 0, y: 0 }
  const home = cellRect(origin, shift(s.cell, o))
  const card = s.at ? { ...home, x: s.at.x, y: s.at.y } : home
  const shown = s.target ?? s.cell
  const slot = Boolean(s.target && (s.target.col !== s.cell.col || s.target.row !== s.cell.row))
  const slotR = cellRect(origin, shift(slot ? s.target! : s.cell, o))
  return { compact, o, card, shown, slot, slotR }
}
</script>

<template>
  <Stage
    :width="550"
    :height="360"
    :initial="{ cell: START, lifted: false, at: null, target: null, avail: idle, focus: null }"
    :script="script"
    :poster="{ cell: END, lifted: false, at: null, target: null, avail: ['ok', 'ok', 'ok'], focus: null }"
    :cursor="{ at: 'rest' }"
    :compact="{ below: 560, width: 358, height: 380 }"
    keys="bottom-right"
    class="cal"
    v-slot="{ state: s, layout }"
  >
    <Camera :focus="s.focus" :max="1.35" :pad="0">
      <Window
        class="cal-window"
        :data-layout="layout"
        title="October 2026"
      >
        <template #toolbar>
          <span class="cal-tools">
            <span class="cal-today">Today</span>
            <Icon name="chevron-right" :size="14" class="cal-prev" />
            <Icon name="chevron-right" :size="14" />
          </span>
        </template>
        <div class="cal-head">
          <span
            v-for="(d, i) in DAYS.slice(sceneGeo(s, layout).o)"
            :key="d"
            :data-today="i + sceneGeo(s, layout).o === 3 || undefined"
          >
            {{ d }}
          </span>
        </div>
        <div class="cal-body">
          <div class="cal-hours">
            <span v-for="h in HOURS" :key="h">{{ h }}</span>
          </div>
          <div class="cal-grid" data-target="grid">
            <span
              v-for="([c, r, n, w], i) in BUSY.filter(([c]) => c >= sceneGeo(s, layout).o)"
              :key="i"
              class="cal-busy"
              :style="{
                left: `${(c - sceneGeo(s, layout).o) * COL_W + 3}px`,
                top: `${r * ROW_H + 2}px`,
                width: `${COL_W - 6}px`,
                height: `${n * ROW_H - 4}px`,
              }"
            >
              <Bar :w="w" :h="5" :tone="3" />
            </span>
            <div
              class="cal-slot"
              :data-show="sceneGeo(s, layout).slot || undefined"
              :style="{
                transform: `translate(${sceneGeo(s, layout).slotR.x}px, ${sceneGeo(s, layout).slotR.y}px)`,
                width: `${sceneGeo(s, layout).slotR.width}px`,
                height: `${sceneGeo(s, layout).slotR.height}px`,
              }"
            />
            <div
              class="cal-event"
              data-target="event"
              data-cursor="open"
              :data-lifted="s.lifted || undefined"
              :data-dragging="s.at ? true : undefined"
              :style="{
                translate: `${sceneGeo(s, layout).card.x}px ${sceneGeo(s, layout).card.y}px`,
                transformOrigin: `${GRIP.x * 100}% ${GRIP.y * 100}%`,
                width: `${sceneGeo(s, layout).card.width}px`,
                height: `${sceneGeo(s, layout).card.height}px`,
              }"
            >
              <span class="cal-event__title">Roadmap sync</span>
              <span class="cal-event__time">
                <Roll variant="fade" :text="span(sceneGeo(s, layout).shown)" />
              </span>
              <span class="cal-event__people">
                <span v-for="(p, i) in PEOPLE" :key="p" class="cal-person">
                  <Avatar :name="p" :size="20" :tone="s.avail[i] === 'ok' ? 'success' : 'ink'" />
                  <svg class="cal-ring" :data-state="s.avail[i]" viewBox="0 0 26 26" width="26" height="26" aria-hidden="true">
                    <circle class="cal-ring__arc" cx="13" cy="13" r="11.5" pathLength="1" />
                  </svg>
                </span>
              </span>
            </div>
          </div>
        </div>
      </Window>

      <span data-target="rest" :style="{ position: 'absolute', left: `${sceneGeo(s, layout).compact ? 300 : 486}px`, top: `${sceneGeo(s, layout).compact ? 296 : 312}px` }" />
      <span data-target="aside" :style="{ position: 'absolute', left: `${sceneGeo(s, layout).compact ? 314 : 446}px`, top: `${sceneGeo(s, layout).compact ? 250 : 196}px` }" />
    </Camera>
  </Stage>
</template>
