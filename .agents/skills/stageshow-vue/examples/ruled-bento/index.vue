<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Count, Icon, Meter, Prompt, Caret, Stage, States, Window, useReducedMotion } from '../../kit'
import type { Act } from '../../kit'
import './grid.css'

// A ruled bento on dark: the features section of Halite, an invented edge
// database. One rounded container, 1px rules between the cells, no gaps,
// mixed spans (2 + 1, then 1 + 2, then a full-width band), the way Linear,
// Framer and Raycast's developer page set theirs.
//
//   Tile      Span   Kind        The one thing                         Moves
//   Create    2 × 1  Hero UI     `halite create`, the only window      the migration bar fills, Ready prints
//   Reads     1 × 1  Stat        "4ms" at the median                   counts down from 120
//   Regions   1 × 1  Diagram     a primary and six replicas            the lines draw out, replicas light
//   Restore   2 × 1  Component   the restore scrubber                  the handle slides back past the bad drop
//   Drivers   3 × 1  Collection  ORM names, bleeding off both sides    the rows drift apart
//
// Two of five tiles are UI, one window. Across and down, no kind sits next
// to itself. Each picture is its own Stage at 1:1, pinned to its cell's
// bottom; the copy is page text. Each cell plays one beat, once, 110ms
// after the one before it in reading order.

const STEP = 110
const LEAD = 450

type Beat = { on: boolean; fill?: boolean }
const before: Beat = { on: false }
const after: Beat = { on: true, fill: true }
const beat = (i: number) => async (a: Act<Beat>) => {
  await a.wait(LEAD + i * STEP)
  await a.set({ on: true })
}

// Measure the tile, not the page: a wide page can still contain a narrow tile.
function usePictureWidth() {
  const elRef = ref<HTMLDivElement | null>(null)
  const width = ref(340)
  let observer: ResizeObserver | null = null
  onMounted(() => {
    const node = elRef.value
    if (!node) return
    const measure = () => {
      width.value = node.clientWidth
    }
    measure()
    observer = new ResizeObserver(measure)
    observer.observe(node)
  })
  onUnmounted(() => {
    observer?.disconnect()
  })
  return [elRef, width] as const
}

function useInView(delay: number) {
  const elRef = ref<HTMLDivElement | null>(null)
  const seen = ref(false)
  let io: IntersectionObserver | null = null
  let t = 0
  onMounted(() => {
    const el = elRef.value
    if (!el) return
    io = new IntersectionObserver(
      ([e]) => {
        if (!e?.isIntersecting) return
        io?.disconnect()
        t = window.setTimeout(() => {
          seen.value = true
        }, delay)
      },
      { threshold: 0.4 },
    )
    io.observe(el)
  })
  onUnmounted(() => {
    io?.disconnect()
    clearTimeout(t)
  })
  return [elRef, seen] as const
}

/* ---------------- Create (hero) ---------------- */

const create = async (a: Act<Beat>) => {
  await a.wait(LEAD)
  await a.set({ on: true })
  await a.wait(800)
  await a.set({ on: true, fill: true })
}

const [heroRef, heroWidth] = usePictureWidth()

/* ---------------- Reads (stat) ---------------- */

const reduced = useReducedMotion()
const [statRef, statSeen] = useInView(LEAD + STEP)

/* ---------------- Regions (diagram) ---------------- */

// Rough world positions on a 380 × 236 stage, the primary in Virginia
// Every pill stays inside x 46 to 334, the part the narrowest cell shows
const PRIMARY = { id: 'iad1', x: 124, y: 96 }
const REPLICAS = [
  { id: 'sfo1', x: 62, y: 58 },
  { id: 'gru1', x: 148, y: 196 },
  { id: 'lhr1', x: 196, y: 40 },
  { id: 'fra1', x: 232, y: 86 },
  { id: 'sin1', x: 270, y: 146 },
  { id: 'syd1', x: 286, y: 204 },
]

function arc(a: { x: number; y: number }, b: { x: number; y: number }) {
  // A gentle bow above the straight line, more for longer runs
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2
  const d = Math.hypot(b.x - a.x, b.y - a.y)
  return `M${a.x} ${a.y} Q${mx} ${my - d * 0.22} ${b.x} ${b.y}`
}

const [mapRef, mapWidth] = usePictureWidth()
const mapPoint = (p: typeof PRIMARY, w: number) => ({
  ...p,
  x: w < 360 ? 38 + ((p.x - 62) / 224) * (w - 106) : p.x + (w - 380) / 2,
})

/* ---------------- Restore (component) ---------------- */

// Write activity per minute, 13:00 to 14:40: varied, with a quiet lunch dip
const WRITES = Array.from({ length: 50 }, (_, i) => {
  const base = 0.38 + 0.3 * Math.sin(i * 0.37) * Math.cos(i * 0.11) + 0.18 * Math.sin(i * 1.7)
  const dip = i > 14 && i < 22 ? 0.45 : 1
  return Math.max(0.12, Math.min(1, base * dip + 0.12))
})
// Two minutes a bar from 13:00: the handle stops at 14:02, the table went at 14:04
const DROP = 31

const [restoreRef, restoreWidth] = usePictureWidth()

/* ---------------- Drivers (collection) ---------------- */

const ROWS = [
  ['ecto', 'prisma', 'drizzle', 'kysely', 'sqlalchemy', 'gorm', 'diesel', 'sequelize', 'typeorm', 'exposed'],
  ['knex', 'active record', 'sqlx', 'django', 'jooq', 'ent', 'mikro-orm', 'hibernate', 'pgx', 'slonik'],
  ['dapper', 'peewee', 'objection', 'bun', 'sqlc', 'psycopg', 'tortoise', 'doctrine', 'ebean', 'room'],
]

const beat2 = beat(2)
const beat3 = beat(3)
const beat4 = beat(4)
</script>

<template>
  <div class="ruled-bento">
    <div class="rb-grid">
      <!-- Create (hero) -->
      <section class="rb-cell rb-cell--hero" data-crop>
        <p class="rb-copy">
          <b>A database in one command.</b> Halite provisions it, runs your migrations and hands back a URL.
        </p>
        <div
          ref="heroRef"
          class="rb-picture rb-picture--hero"
          :style="{ '--rb-picture-width': `${heroWidth}px` }"
        >
          <Stage
            :width="heroWidth"
            :height="300"
            theme="dark"
            :initial="before"
            :poster="after"
            play="once"
            :script="create"
            class="rb-stage"
            v-slot="{ state: s }"
          >
            <Window
              chrome="terminal"
              lights="grey"
              :title="heroWidth >= 600 ? 'demo — zsh' : undefined"
              class="rb-term"
              :body="{ 'data-crop': '' }"
              :data-on="s.on || undefined"
              :data-fill="s.fill || undefined"
              :data-layout="heroWidth < 600 ? 'compact' : 'wide'"
            >
              <div class="ss-term rb-term__body">
                <Prompt path="~/demo">halite create shop</Prompt>
                <div class="rb-out" :style="{ '--i': 0 }">
                  <span class="dim">Created</span> shop <span class="dim">in</span> iad1
                </div>
                <div class="rb-out rb-migrate" :style="{ '--i': 1 }">
                  <span class="dim">Migrating</span>
                  <Meter class="rb-meter" :value="s.fill ? 1 : 0" />
                  <span class="rb-count">
                    <Count :value="s.fill ? 14 : 0" :duration="1000" />
                    <span class="dim">/14</span>
                  </span>
                </div>
                <div class="rb-out rb-ready" :style="{ '--i': 2 }">
                  <span class="ok">✓</span> Ready <span class="dim">in 1.9s</span>
                </div>
                <div class="rb-out rb-url" :style="{ '--i': 3 }">
                  <span class="dim">{{ heroWidth >= 600 ? 'DATABASE_URL  ' : '' }}</span>
                  {{ heroWidth >= 600 ? 'halite://shop.demo.example' : 'halite://shop.demo…' }}
                </div>
                <Prompt path="~/demo" class="rb-out" :style="{ '--i': 4 }">
                  <Caret />
                </Prompt>
              </div>
            </Window>
          </Stage>
        </div>
      </section>

      <!-- Reads (stat) -->
      <section class="rb-cell rb-cell--stat" data-crop>
        <div ref="statRef" class="rb-stat">
          <span class="rb-stat-lead">
            <Icon name="bolt" filled :size="16" class="rb-bolt" />
            Reads in
          </span>
          <span class="rb-stat-number">
            <Count :value="statSeen || reduced ? 4 : 0" :duration="1300" />
            <span class="rb-stat-unit">ms</span>
          </span>
          <span class="rb-stat-label">at the median, from the replica nearest each user.</span>
        </div>
      </section>

      <!-- Regions (diagram) -->
      <section class="rb-cell rb-cell--map" data-crop>
        <p class="rb-copy">
          <b>Replicas near every user.</b> Reads never cross an ocean.
        </p>
        <div ref="mapRef" class="rb-picture rb-picture--map">
          <Stage
            :width="mapWidth"
            :height="236"
            theme="dark"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat2"
            class="rb-stage"
            v-slot="{ state: s }"
          >
            <div class="rb-map" :data-on="s.on || undefined">
              <svg class="rb-map__lines" :width="mapWidth" :height="236" aria-hidden="true">
                <g
                  v-for="(r, i) in REPLICAS.map((rp) => mapPoint(rp, mapWidth))"
                  :key="r.id"
                  :style="{ '--i': i }"
                >
                  <path :d="arc(mapPoint(PRIMARY, mapWidth), r)" class="rb-arc" />
                  <path :d="arc(mapPoint(PRIMARY, mapWidth), r)" class="rb-arc rb-arc--lit" pathLength="1" />
                </g>
              </svg>
              <span
                class="rb-node"
                data-primary
                :style="{ left: `${mapPoint(PRIMARY, mapWidth).x}px`, top: `${mapPoint(PRIMARY, mapWidth).y}px` }"
              >
                <span class="rb-node__dot" />
                {{ PRIMARY.id }}
              </span>
              <span
                v-for="(r, i) in REPLICAS.map((rp) => mapPoint(rp, mapWidth))"
                :key="r.id"
                class="rb-node"
                :style="{ left: `${r.x}px`, top: `${r.y}px`, '--i': i }"
              >
                <span class="rb-node__dot" />
                {{ r.id }}
              </span>
            </div>
          </Stage>
        </div>
      </section>

      <!-- Restore (component) -->
      <section class="rb-cell rb-cell--restore" data-crop>
        <p class="rb-copy">
          <b>Undo the bad migration.</b> Rewind to any second in the last 30 days.
        </p>
        <div ref="restoreRef" class="rb-picture rb-picture--restore">
          <Stage
            :width="restoreWidth"
            :height="restoreWidth < 600 ? 236 : 216"
            theme="dark"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat3"
            class="rb-stage"
            v-slot="{ state: s }"
          >
            <div
              class="rb-restore"
              :data-on="s.on || undefined"
              :data-layout="restoreWidth < 600 ? 'compact' : 'wide'"
            >
              <div class="rb-restore__head">
                <span class="rb-restore__label">Restore shop to</span>
                <States
                  :value="s.on ? 'then' : 'now'"
                  align="start"
                  class="rb-restore__time"
                  :states="{ now: 'Now', then: '14:02:59' }"
                />
              </div>
              <div
                class="rb-track"
                :style="{
                  '--n': (restoreWidth >= 600 ? WRITES : WRITES.slice(22, 46)).length,
                  '--drop': restoreWidth >= 600 ? DROP : DROP - 22,
                }"
              >
                <span
                  v-for="(h, i) in (restoreWidth >= 600 ? WRITES : WRITES.slice(22, 46))"
                  :key="i"
                  class="rb-track__bar"
                  :data-after="i >= (restoreWidth >= 600 ? DROP : DROP - 22) || undefined"
                  :style="{ height: `${Math.round(h * 100)}%` }"
                />
                <span class="rb-event">
                  <span class="rb-event__tag">DROP TABLE carts</span>
                </span>
                <span class="rb-handle" />
              </div>
              <div
                class="rb-axis"
                :style="{ '--n': (restoreWidth >= 600 ? WRITES : WRITES.slice(22, 46)).length }"
              >
                <span
                  v-for="[t, at] in (restoreWidth >= 600
                    ? [['13:00', 0], ['13:30', 15], ['14:00', 30]]
                    : [['13:50', 3], ['14:10', 13]])"
                  :key="t"
                  :style="{ '--at': at }"
                >
                  {{ t }}
                </span>
              </div>
            </div>
          </Stage>
        </div>
      </section>

      <!-- Drivers (collection) -->
      <section class="rb-cell rb-cell--orm" data-crop>
        <p class="rb-copy">
          <b>Bring your ORM.</b> Halite speaks the Postgres wire protocol, so your driver already works.
        </p>
        <div class="rb-picture rb-picture--orm">
          <Stage
            :width="1200"
            :height="150"
            theme="dark"
            :initial="before"
            :poster="after"
            play="once"
            :script="beat4"
            class="rb-stage"
            v-slot="{ state: s }"
          >
            <div class="rb-rows" :data-on="s.on || undefined">
              <div
                v-for="(row, r) in ROWS"
                :key="r"
                class="rb-row"
                :style="{ '--dir': r % 2 ? 1 : -1, '--off': `${[-40, -96, -12][r]}px` }"
              >
                <span v-for="name in row" :key="name" class="rb-chip">
                  {{ name }}
                </span>
              </div>
            </div>
          </Stage>
        </div>
      </section>
    </div>
  </div>
</template>
