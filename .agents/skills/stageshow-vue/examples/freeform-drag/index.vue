<script setup lang="ts">
import { Stage, Window, Bar, Avatar, cellOf, type Act, type Point, type Rect } from '../../kit'
import './drag.css'

// Freeform drag with a drop target. The card follows the cursor exactly; the
// dashed slot shows where it will land. As in real calendars, the slot never
// travels: it appears in the landing cell, jumps straight to the next cell
// when that changes, and is hidden while the card is still over its own cell.
// Anything that slides after the card reads as a second object chasing it.
// cellOf makes cell borders sticky, so a drag along a border doesn't flicker.

const COLS = 4
const ROWS = 6
const COL_W = 104
const ROW_H = 40
const START = { col: 1, row: 3 }
const END = { col: 2, row: 1 }

type Cell = { col: number; row: number }
type S = { cell: Cell; lifted: boolean; at: Point | null; target: Cell | null }

const cellRect = (grid: Rect, c: Cell): Rect => ({
  x: grid.x + c.col * COL_W + 3,
  y: grid.y + c.row * ROW_H + 2,
  width: COL_W - 6,
  height: ROW_H * 2 - 4,
})

async function move(a: Act<S>, from: Cell, to: Cell) {
  const grid = a.rect('grid', { layout: true })
  const card = cellRect(grid, from)
  const grab = { x: card.x + card.width * 0.35, y: card.y + 22 }
  await a.move(grab)
  const dest = cellRect(grid, to)
  let prev: Cell = from
  await a.drag(
    { x: dest.x + (grab.x - card.x), y: dest.y + (grab.y - card.y) },
    (p) => {
      const at = { x: p.x - (grab.x - card.x), y: p.y - (grab.y - card.y) }
      // The card's center decides the cell, with sticky borders
      const col = cellOf(at.x + card.width / 2 - grid.x, COL_W, prev.col)
      const row = cellOf(at.y + ROW_H / 2 - grid.y, ROW_H, prev.row)
      prev = { col: Math.max(0, Math.min(COLS - 1, col)), row: Math.max(0, Math.min(ROWS - 2, row)) }
      // drag() has pressed and closed the hand before its first callback.
      // Pick up and move in that same frame, never while the hand is open.
      a.put({ lifted: true, at, target: prev })
    },
    { duration: 1100 },
  )
  await a.set({ lifted: false, at: null, target: null, cell: prev })
}

const script = async (a: Act<S>) => {
  await a.wait(500)
  await move(a, START, END)
  await a.wait(1200)
  // Back again: a caused reset, and a second diagonal in the other direction
  await move(a, END, START)
  await a.move('rest')
  await a.wait(600)
}

// Friday runs off the window's right edge, so the grid never stops short
const DAYS = ['Mon 20', 'Tue 21', 'Wed 22', 'Thu 23', 'Fri 24']
const HOURS = ['9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM']
const BUSY: [number, number, number][] = [
  [0, 0, 2],
  [3, 1, 1],
  [0, 4, 1],
  [3, 3, 2],
]

function getCard(s: S, grid: Rect): Rect {
  return s.at ? { ...cellRect(grid, s.cell), x: s.at.x, y: s.at.y } : cellRect(grid, s.cell)
}

function getTargetShow(s: S, grid: Rect): boolean {
  return Boolean(s.target && grid.width && (s.target.col !== s.cell.col || s.target.row !== s.cell.row))
}

function getTargetRect(s: S, grid: Rect): Rect {
  const show = getTargetShow(s, grid)
  return cellRect(grid, show ? s.target! : s.cell)
}
</script>

<template>
  <Stage
    :width="560"
    :height="340"
    :compact="{ below: 500, width: 358, height: 340 }"
    :initial="({ cell: START, lifted: false, at: null, target: null } as S)"
    :poster="({ cell: END, lifted: false, at: null, target: null } as S)"
    :script="script"
    :cursor="{ at: 'rest' }"
    class="fd"
    v-slot="{ state: s, rect, layout }"
  >
    <Window title="Calendar" class="fd-window">
      <div class="fd-head">
        <span v-for="d in DAYS" :key="d">{{ d }}</span>
      </div>
      <div class="fd-body">
        <div class="fd-hours">
          <span v-for="h in HOURS" :key="h">{{ h }}</span>
        </div>
        <div class="fd-grid" data-target="grid">
          <span
            v-for="([c, r, span], i) in BUSY"
            :key="i"
            class="fd-busy"
            :style="{
              left: `${c * COL_W + 3}px`,
              top: `${r * ROW_H + 2}px`,
              width: `${COL_W - 6}px`,
              height: `${span * ROW_H - 4}px`,
            }"
          >
            <Bar :w="40 + ((i * 17) % 24)" :h="5" :tone="3" />
          </span>
        </div>
      </div>
    </Window>
    <div
      class="fd-target"
      :data-show="getTargetShow(s, rect('grid')) || undefined"
      :style="{
        transform: `translate(${getTargetRect(s, rect('grid')).x}px, ${getTargetRect(s, rect('grid')).y}px)`,
        width: `${getTargetRect(s, rect('grid')).width}px`,
        height: `${getTargetRect(s, rect('grid')).height}px`,
      }"
    />
    <div
      class="fd-card"
      data-target="meeting"
      data-cursor="open"
      :data-lifted="s.lifted || undefined"
      :data-dragging="s.at ? true : undefined"
      :style="{
        translate: `${getCard(s, rect('grid')).x}px ${getCard(s, rect('grid')).y}px`,
        width: `${getCard(s, rect('grid')).width}px`,
        height: `${getCard(s, rect('grid')).height}px`,
        transformOrigin: '35% 22px',
      }"
    >
      <span class="fd-card__title">Design review</span>
      <span class="fd-card__people">
        <Avatar name="M" :size="16" />
        <Avatar name="J" :size="16" />
      </span>
    </div>
    <span data-target="rest" :style="{ position: 'absolute', left: `${layout === 'compact' ? 330 : 500}px`, top: '300px' }" />
  </Stage>
</template>
