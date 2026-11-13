<script setup lang="ts">
import { Bar, Field, Popover, Stage, Window, type Act, type Layout, BrandMark, Toast } from '../../kit'
import './gcal.css'

// Google Calendar, week view. Context: a quiet week with today marked.
// Action: drag across an empty Thursday afternoon, the quick-create popup
// opens, a title is typed and saved. Result: the event settles into the grid
// and the "Event saved" snackbar offers Undo, which is the loop's reset.

type S = {
  draft: { show: boolean; start: number; end: number }
  saved: boolean
  pop: { show: boolean; x: number; y: number }
  focused: boolean
  title: string
  snack: boolean
}

const initial: S = {
  draft: { show: false, start: 780, end: 810 },
  saved: false,
  pop: { show: false, x: -1000, y: 0 },
  focused: false,
  title: '',
  snack: false,
}

// Reduced motion shows the payoff: the event saved into the grid
const poster: S = { ...initial, draft: { show: true, start: 780, end: 870 }, saved: true, title: 'Design review' }

// Geometry per layout. Minutes are from midnight.
const GEO = {
  wide: { stage: { w: 800, h: 460 }, gutter: 36, hour: 44, from: 10 * 60, rows: 10, today: 4, popW: 352 },
  compact: { stage: { w: 400, h: 380 }, gutter: 16, hour: 40, from: 10 * 60, rows: 9, today: 0, popW: 220 },
} as const

const WEEK = [
  { d: 'SUN', n: 18 },
  { d: 'MON', n: 19 },
  { d: 'TUE', n: 20 },
  { d: 'WED', n: 21 },
  { d: 'THU', n: 22 },
  { d: 'FRI', n: 23 },
  { d: 'SAT', n: 24 },
]
// 4-day view starts on today, as Google Calendar's does
const FOUR = WEEK.slice(4).concat([{ d: 'SUN', n: 25 }])

// Existing events, by date: [date, start, end, bar widths]
const EVENTS: [number, number, number, number[]][] = [
  [19, 600, 660, [44, 28]],
  [20, 690, 750, [52, 30]],
  [20, 930, 990, [38, 26]],
  [21, 630, 690, [48, 24]],
  [22, 600, 645, [40]],
  [22, 960, 1050, [46, 28]],
  [23, 720, 780, [50, 30]],
  [24, 660, 720, [36, 24]],
  [25, 750, 810, [44, 26]],
]

const NOW = 11 * 60 + 20
const DAY = 22

const hourLabel = (m: number) => {
  const h = Math.floor(m / 60)
  return `${h % 12 || 12} ${h < 12 ? 'AM' : 'PM'}`
}
const clockFmt = (m: number, suffix = true) => {
  const h = Math.floor(m / 60)
  const min = m % 60
  const t = `${h % 12 || 12}${min ? `:${String(min).padStart(2, '0')}` : ''}`
  return suffix ? `${t}${h < 12 ? 'am' : 'pm'}` : t
}
const range = (a: number, b: number) => {
  const samehalf = (a < 720) === (b < 720)
  return `${samehalf ? clockFmt(a, false) : clockFmt(a)} – ${clockFmt(b)}`
}
const clockFull = (m: number) => {
  const h = Math.floor(m / 60)
  return `${h % 12 || 12}:${String(m % 60).padStart(2, '0')}${h < 12 ? 'am' : 'pm'}`
}

const MINI_DAYS: { n: number; out?: boolean }[] = [
  ...[27, 28, 29, 30].map((n) => ({ n, out: true })),
  ...Array.from({ length: 31 }, (_, i) => ({ n: i + 1 })),
]

const SIDE_CALS: [string, number][] = [
  ['#039be5', 70],
  ['#33b679', 54],
  ['#8e24aa', 62],
]

async function script(a: Act<S>) {
  const g = GEO[a.layout]
  const col = a.rect('today-col')
  const y = (m: number) => col.y + ((m - g.from) / 60) * g.hour
  const snap = (py: number) => g.from + Math.round((((py - col.y) / g.hour) * 60) / 15) * 15

  await a.wait(700)

  // 1. Drag down Thursday afternoon, 1:00 to 2:30
  a.mark('drag')
  const from = { x: col.x + col.width * 0.8, y: y(780) + 3 }
  const to = { x: col.x + col.width * 0.8, y: y(870) - 2 }
  // Google Calendar keeps the arrow through the press and drag-creation.
  await a.move(from)
  await a.wait(250)
  await a.drag(
    to,
    (at) => {
      const end = Math.max(810, Math.min(870, snap(at.y + 6)))
      a.put({ draft: { show: true, start: 780, end } })
    },
    { duration: 900, cursor: 'preserve' },
  )
  await a.set({ draft: { show: true, start: 780, end: 870 } })
  await a.wait(200)

  // 2. The quick-create popup opens beside the new block
  a.mark('popup')
  const block = a.rect('draft')
  const pop = a.rect('popup', { layout: true })
  const px = a.layout === 'wide' ? block.x - 32 - pop.width : block.x + block.width + 8
  const py = Math.max(g.gutter, Math.min(block.y - 64, g.stage.h - g.gutter - (a.layout === 'wide' ? 8 : 0) - pop.height))
  await a.snap({ pop: { show: false, x: px, y: py } }, 'popup')
  await a.set({ pop: { show: true, x: px, y: py }, focused: true })
  await a.wait(500)

  // 3. Type a title
  await a.type('title', 'Design review', { interval: 70 })
  await a.wait(500)

  // 4. Save: the popup closes and the block settles into the grid
  a.mark('save')
  await a.move({ at: 'save', x: 0.82, y: 0.62 })
  await a.wait(250)
  await a.click()
  await a.set((s) => ({ pop: { ...s.pop, show: false }, focused: false, saved: true }))
  await a.wait(450)
  await a.set({ snack: true })
  await a.wait(2400)

  // 5. Undo, the caused reset
  a.mark('undo')
  await a.move({ at: 'undo', x: 0.9, y: 0.88 })
  await a.wait(300)
  await a.click()
  await a.set((s) => ({ draft: { ...s.draft, show: false }, snack: false }))
  await a.move('rest')
  await a.wait(600)
  await a.snap({ ...initial })
  await a.wait(300)
}

/* ---- Material icons (the product's set), 24 grid ---- */

const MI = {
  menu: 'M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z',
  left: 'M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z',
  right: 'M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z',
  search:
    'M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  help:
    'M11 18h2v-2h-2v2zm1-16C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z',
  apps: 'M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z',
  drop: 'M7 10l5 5 5-5z',
  add: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
  close: 'M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  handle: 'M20 9H4v2h16V9zM4 15h16v-2H4v2z',
  schedule:
    'M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z',
  people:
    'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z',
  check: 'M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z',
  event:
    'M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z',
} as const

function gridInfo(s: S, layout: Layout) {
  const g = GEO[layout]
  const wide = layout === 'wide'
  const days = wide ? WEEK : FOUR
  const top = (m: number) => ((m - g.from) / 60) * g.hour
  const hours = Array.from({ length: g.rows }, (_, i) => g.from + i * 60)
  const dur = s.draft.end - s.draft.start
  const label = s.title || '(No title)'
  return { g, wide, days, top, hours, dur, label }
}
</script>

<template>
  <Stage
    :width="GEO.wide.stage.w"
    :height="GEO.wide.stage.h"
    :compact="{ below: 560, width: GEO.compact.stage.w, height: GEO.compact.stage.h }"
    :initial="initial"
    :poster="poster"
    :script="script"
    accent="#0b57d0"
    :cursor="{ at: 'rest' }"
    class="gc-stage"
    v-slot="{ state: s, layout }"
  >
    <template v-for="info in [gridInfo(s, layout)]" :key="layout">
      <Window url="calendar.google.com/calendar/u/0/r/week" url-shape="pill" class="gc-window" :data-layout="layout">
        <div class="gc-app">
          <header class="gc-header">
            <div class="gc-brand">
              <span class="gc-iconbtn">
                <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
                  <path :d="MI.menu" fill="currentColor" />
                </svg>
              </span>
              <BrandMark brand="google-calendar" :tile="false" :size="26" class="gc-mark" />
              <span v-if="info.wide" class="gc-brand-name">Calendar</span>
            </div>
            <span class="gc-today">Today</span>
            <span class="gc-arrows">
              <span class="gc-iconbtn sm">
                <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
                  <path :d="MI.left" fill="currentColor" />
                </svg>
              </span>
              <span class="gc-iconbtn sm">
                <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
                  <path :d="MI.right" fill="currentColor" />
                </svg>
              </span>
            </span>
            <span class="gc-month">October 2026</span>
            <span v-if="info.wide" class="gc-tools">
              <span class="gc-iconbtn">
                <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
                  <path :d="MI.search" fill="currentColor" />
                </svg>
              </span>
              <span class="gc-iconbtn">
                <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
                  <path :d="MI.help" fill="currentColor" />
                </svg>
              </span>
              <span class="gc-view">
                Week
                <svg viewBox="0 0 24 24" width="18" height="18" class="gc-icon" aria-hidden="true">
                  <path :d="MI.drop" fill="currentColor" />
                </svg>
              </span>
              <span class="gc-switch">
                <span>
                  <svg viewBox="0 0 24 24" width="18" height="18" class="gc-icon" aria-hidden="true">
                    <path :d="MI.event" fill="currentColor" />
                  </svg>
                </span>
                <span>
                  <svg viewBox="0 0 24 24" width="18" height="18" class="gc-icon" aria-hidden="true">
                    <path :d="MI.check" fill="currentColor" />
                  </svg>
                </span>
              </span>
              <span class="gc-iconbtn">
                <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
                  <path :d="MI.apps" fill="currentColor" />
                </svg>
              </span>
              <span class="gc-avatar" />
            </span>
          </header>

          <div class="gc-main">
            <aside v-if="info.wide" class="gc-side">
              <span class="gc-create">
                <svg viewBox="0 0 24 24" width="22" height="22" class="gc-icon gc-create-plus" aria-hidden="true">
                  <path :d="MI.add" fill="currentColor" />
                </svg>
                Create
                <svg viewBox="0 0 24 24" width="18" height="18" class="gc-icon" aria-hidden="true">
                  <path :d="MI.drop" fill="currentColor" />
                </svg>
              </span>
              <div class="gc-mini">
                <div class="gc-mini-head">
                  <span>October 2026</span>
                  <span class="gc-mini-nav">
                    <svg viewBox="0 0 24 24" width="16" height="16" class="gc-icon" aria-hidden="true">
                      <path :d="MI.left" fill="currentColor" />
                    </svg>
                    <svg viewBox="0 0 24 24" width="16" height="16" class="gc-icon" aria-hidden="true">
                      <path :d="MI.right" fill="currentColor" />
                    </svg>
                  </span>
                </div>
                <div class="gc-mini-grid">
                  <span v-for="(d, i) in ['S', 'M', 'T', 'W', 'T', 'F', 'S']" :key="`h${i}`" class="gc-mini-dow">
                    {{ d }}
                  </span>
                  <span
                    v-for="(d, i) in MINI_DAYS"
                    :key="i"
                    class="gc-mini-day"
                    :data-out="d.out || undefined"
                    :data-today="(!d.out && d.n === DAY) || undefined"
                  >
                    {{ d.n }}
                  </span>
                </div>
              </div>
              <div class="gc-cals">
                <div class="gc-cals-head">
                  <Bar :w="72" :h="6" :tone="4" />
                </div>
                <div v-for="([c, w], i) in SIDE_CALS" :key="i" class="gc-cal">
                  <span class="gc-check" :style="{ background: c }" />
                  <Bar :w="w" :h="6" :tone="3" />
                </div>
              </div>
            </aside>

            <section class="gc-panel" :style="{ ['--days' as string]: info.days.length, ['--hour' as string]: `${info.g.hour}px` }">
              <div class="gc-dayhead">
                <span class="gc-tz">GMT-07</span>
                <span v-for="d in info.days" :key="d.n" class="gc-dayname" :data-today="d.n === DAY || undefined">
                  <span class="gc-dow">{{ d.d }}</span>
                  <span class="gc-date">{{ d.n }}</span>
                </span>
              </div>
              <div class="gc-body" data-crop>
                <div class="gc-gutter">
                  <span v-for="(m, i) in info.hours" :key="m" class="gc-hour" :style="{ top: `${i * info.g.hour}px` }">
                    <template v-if="i > 0">{{ hourLabel(m) }}</template>
                  </span>
                </div>
                <div v-for="d in info.days" :key="d.n" class="gc-col" :data-target="d.n === DAY ? 'today-col' : undefined">
                  <div
                    v-for="([, a, b, bars], i) in EVENTS.filter((e) => e[0] === d.n)"
                    :key="i"
                    class="gc-event"
                    :data-past="d.n < DAY || (d.n === DAY && b <= NOW) || undefined"
                    :style="{ top: `${info.top(a) + 1}px`, height: `${info.top(b) - info.top(a) - 2}px` }"
                  >
                    <Bar v-for="(w, j) in bars" :key="j" :w="w" :h="5" class="gc-event-bar" :data-sub="j > 0 || undefined" />
                  </div>
                  <span v-if="d.n === DAY + 1" class="gc-rest" data-target="rest" :style="{ top: `${info.top(14 * 60 + 20)}px` }" />
                  <template v-if="d.n === DAY">
                    <span class="gc-now" :style="{ top: `${info.top(NOW)}px` }" />
                    <div
                      class="gc-draft"
                      data-target="draft"
                      :data-show="s.draft.show || undefined"
                      :data-saved="s.saved || undefined"
                      :data-short="info.dur <= 30 || undefined"
                      data-crop
                      :style="{ top: `${info.top(s.draft.start) + 1}px`, height: `${info.top(s.draft.end) - info.top(s.draft.start) - 2}px` }"
                    >
                      <span class="gc-draft-title">{{ info.label }}</span>
                      <span class="gc-draft-time">{{ range(s.draft.start, s.draft.end) }}</span>
                    </div>
                  </template>
                </div>
              </div>
            </section>
          </div>
        </div>
      </Window>

      <Popover
        :show="s.pop.show"
        :origin="info.wide ? 'right center' : 'left center'"
        class="gc-pop"
        data-target="popup"
        :data-layout="layout"
        :style="{ left: `${s.pop.x}px`, top: `${s.pop.y}px`, width: `${info.g.popW}px` }"
      >
        <div class="gc-pop-top">
          <svg viewBox="0 0 24 24" width="18" height="18" class="gc-icon" aria-hidden="true">
            <path :d="MI.handle" fill="currentColor" />
          </svg>
          <span class="gc-iconbtn sm">
            <svg viewBox="0 0 24 24" width="18" height="18" class="gc-icon" aria-hidden="true">
              <path :d="MI.close" fill="currentColor" />
            </svg>
          </span>
        </div>
        <div class="gc-pop-indent">
          <Field class="gc-title" :value="s.title" placeholder="Add title" :focused="s.focused" :box="{ 'data-target': 'title' }" />
          <div class="gc-kinds">
            <span class="gc-kind" data-on>
              Event
            </span>
            <span class="gc-kind">Task</span>
          </div>
        </div>
        <div class="gc-pop-row">
          <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
            <path :d="MI.schedule" fill="currentColor" />
          </svg>
          <div class="gc-pop-time">
            <span>
              {{ info.wide ? 'Thursday, October 22' : 'Thu, Oct 22' }}
              <span class="gc-dot">·</span>
              {{ info.wide ? `${clockFull(s.draft.start)} – ${clockFull(s.draft.end)}` : range(s.draft.start, s.draft.end) }}
            </span>
            <Bar :w="info.wide ? 116 : 84" :h="5" :tone="3" />
          </div>
        </div>
        <div v-if="info.wide" class="gc-pop-row">
          <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
            <path :d="MI.people" fill="currentColor" />
          </svg>
          <Bar :w="64" :h="6" :tone="3" />
        </div>
        <div class="gc-pop-row">
          <svg viewBox="0 0 24 24" width="20" height="20" class="gc-icon" aria-hidden="true">
            <path :d="MI.event" fill="currentColor" />
          </svg>
          <Bar :w="info.wide ? 78 : 60" :h="6" :tone="3" />
          <span class="gc-caldot" />
        </div>
        <div class="gc-pop-foot">
          <span v-if="info.wide" class="gc-more">More options</span>
          <span class="gc-save" data-target="save" data-cursor="hand">
            Save
          </span>
        </div>
      </Popover>

      <Toast
        :show="s.snack"
        :class="['gc-snack', { 'gc-snack--compact': layout === 'compact' }]"
      >
        Event saved
        <template #action>
          <span class="gc-undo" data-target="undo" data-cursor="hand">
            Undo
          </span>
        </template>
      </Toast>
    </template>
  </Stage>
</template>
