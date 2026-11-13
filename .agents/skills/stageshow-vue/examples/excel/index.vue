<script setup lang="ts">
import { Bar, Chart, Count, Stage, Swap, Window, type Act, type Layout } from '../../kit'
import './excel.css'

// Excel for Mac: select B2:B7, click AutoSum, the total lands in B8, the
// chart beside the table gains its data labels and total, then a click on
// B8 shows =SUM(B2:B7) in the formula bar. Cmd+Z undoes it and a click back
// on B2 returns to the opening frame.

const ROWS: [string, number][] = [
  ['North', 48200],
  ['South', 39850],
  ['East', 52410],
  ['West', 61730],
  ['Metro', 44960],
  ['Web', 37040],
]
const SUM = ROWS.reduce((n, [, v]) => n + v, 0) // 284,190
const SHARE = ROWS.map(([, v]) => Math.round((v / SUM) * 100))
const fmt = (n: number) => n.toLocaleString('en-US')

type S = {
  from: number // anchor row (the active cell)
  to: number // the row the selection reaches
  dragging: boolean
  total: boolean
  labels: boolean
  sum: number
}

const initial: S = { from: 2, to: 2, dragging: false, total: false, labels: false, sum: 0 }

// Geometry per layout. Columns: row header, A, B, then the rest.
const GEO = {
  wide: { rowHead: 34, a: 112, b: 104, col: 76, cols: 9, rows: 16, row: 22, head: 20, chart: { left: 330, top: 30, width: 344, height: 236 }, plot: { w: 268, h: 158 } },
  compact: { rowHead: 28, a: 70, b: 78, col: 64, cols: 4, rows: 13, row: 22, head: 20, chart: { left: 188, top: 26, width: 196, height: 176 }, plot: { w: 152, h: 88 } },
}

const MAX = 80000
const ticks = [0, 20000, 40000, 60000, 80000]

async function script(a: Act<S>) {
  await a.wait(500)

  // 1. Select the column: press on B2 and drag down to B7.
  await a.move({ at: 'b2', x: 0.42, y: 0.55 })
  await a.wait(250)
  const rowAt = (y: number) => {
    for (let r = 7; r >= 2; r--) if (y >= a.rect(`b${r}`).y) return r
    return 2
  }
  await a.drag({ at: 'b7', x: 0.42, y: 0.55 }, (at) => a.put({ to: rowAt(at.y), dragging: true }), { duration: 1000 })
  await a.set({ dragging: false })
  await a.wait(500)

  // 2. AutoSum: aim at the sigma, so the label stays readable.
  a.mark('autosum')
  await a.move({ at: 'autosum', x: 0.96, y: 0.7 })
  await a.wait(250)
  await a.click()
  await a.set({ total: true, sum: SUM })

  // 3. The chart picks it up: data labels stagger in as the total counts.
  await a.wait(300)
  await a.set({ labels: true })
  await a.wait(1100)

  // 4. Click the total to read its formula.
  a.mark('formula')
  await a.move({ at: 'b8', x: 0.3, y: 0.62 })
  await a.wait(150)
  await a.click()
  await a.set({ from: 8, to: 8 })
  await a.wait(2400)

  // Undo, then back to B2: the opening frame, caused on screen.
  a.mark('undo')
  await a.key('cmd+z')
  await a.set({ total: false, labels: false })
  await a.wait(500)
  await a.snap({ sum: 0 })
  await a.wait(400)
  await a.move({ at: 'b2', x: 0.35, y: 0.5 })
  await a.wait(120)
  await a.click()
  await a.set({ from: 2, to: 2 })
  await a.wait(900)
}

function sheetInfo(s: S, layout: Layout) {
  const g = GEO[layout]
  const compact = layout === 'compact'
  const top = Math.min(s.from, s.to)
  const bottom = Math.max(s.from, s.to)
  const inSel = (r: number) => r >= top && r <= bottom
  const multi = bottom > top
  const name = s.dragging && multi ? `${bottom - top + 1}R x 1C` : `B${s.from}`
  const formula = s.from === 8 ? (s.total ? '=SUM(B2:B7)' : '') : s.from >= 2 && s.from <= 7 ? String(ROWS[s.from - 2][1]) : ''
  const letters = ['A', 'B', ...'CDEFGHIJK'.slice(0, g.cols).split('')]
  const widths = [g.a, g.b, ...Array(g.cols).fill(g.col)]
  const { w, h } = g.plot
  const n = ROWS.length
  const gap = Math.max(2, Math.round(w / n / 4))
  const bw = (w - gap * (n - 1)) / n
  return { g, compact, top, bottom, inSel, name, formula, letters, widths, w, h, n, gap, bw }
}
</script>

<template>
  <Stage
    :width="860"
    :height="480"
    :compact="{ below: 600, width: 420, height: 400 }"
    :initial="initial"
    :poster="{ ...initial, from: 8, to: 8, total: true, labels: true, sum: SUM }"
    :script="script"
    :cursor="{ at: { at: 'b2', x: 0.35, y: 0.5 } }"
    :keys="{ wide: 'bottom-right', compact: 'bottom-right' }"
    accent="#107c41"
    class="xl-stage"
    v-slot="{ state: s, layout }"
  >
    <Window
      v-for="info in [sheetInfo(s, layout)]"
      :key="layout"
      class="xl-window"
      :data-layout="layout"
    >
      <template #lead>
        <span class="xl-quick">
          <span class="xl-autosave">
            AutoSave
            <span class="xl-switch" />
          </span>
          <template v-if="!info.compact">
            <Bar v-for="i in [0, 1, 2, 3]" :key="i" :w="14" :h="14" :r="3" :tone="3" />
          </template>
        </span>
      </template>

      <template #toolbar>
        <span class="xl-doc">Q3 Sales</span>
        <span v-if="!info.compact" class="xl-search">
          <Bar :w="10" :h="10" :r="5" :tone="3" />
          <Bar :w="90" :h="5" :tone="2" />
        </span>
      </template>

      <!-- Ribbon tabs -->
      <div class="xl-tabs">
        <span
          v-for="(t, i) in (info.compact ? ['Home', 'Insert', 'Draw', 'Formulas', 'Data'] : ['Home', 'Insert', 'Draw', 'Page Layout', 'Formulas', 'Data', 'Review', 'View', 'Automate'])"
          :key="t"
          class="xl-tab"
          :data-active="i === 0 || undefined"
        >
          {{ t }}
        </span>
      </div>

      <!-- Ribbon -->
      <div class="xl-ribbon" data-crop>
        <div class="xl-group">
          <span class="xl-big">
            <Bar :w="24" :h="24" :r="4" :tone="3" />
            <span class="xl-big-label">Paste</span>
          </span>
          <span class="xl-stack">
            <Bar :w="14" :h="14" :r="3" :tone="2" />
            <Bar :w="14" :h="14" :r="3" :tone="2" />
          </span>
        </div>
        <div class="xl-group xl-font">
          <span class="xl-row">
            <span class="xl-field" :style="{ width: `${info.compact ? 104 : 112}px` }">
              Aptos Narrow<svg class="xl-caret" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
                <path d="M1.5 3 4 5.5 6.5 3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <span class="xl-field" :style="{ width: '40px' }">
              12<svg class="xl-caret" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
                <path d="M1.5 3 4 5.5 6.5 3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
          </span>
          <span class="xl-row">
            <span class="xl-glyph" :style="{ fontWeight: 700 }">B</span>
            <span class="xl-glyph" :style="{ fontStyle: 'italic', fontFamily: 'Georgia, serif' }">I</span>
            <span class="xl-glyph" :style="{ textDecoration: 'underline' }">U</span>
            <template v-if="!info.compact">
              <span class="xl-sep" />
              <Bar :w="14" :h="14" :r="3" :tone="2" />
              <Bar :w="14" :h="14" :r="3" :tone="2" />
              <Bar :w="14" :h="14" :r="3" :tone="2" />
            </template>
          </span>
        </div>
        <template v-if="!info.compact">
          <div class="xl-group xl-grid2">
            <Bar v-for="i in [0, 1, 2, 3, 4, 5]" :key="i" :w="14" :h="14" :r="3" :tone="2" />
          </div>
          <div class="xl-group xl-font">
            <span class="xl-row">
              <span class="xl-field" :style="{ width: '92px' }">
                General<svg class="xl-caret" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
                  <path d="M1.5 3 4 5.5 6.5 3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </span>
            </span>
            <span class="xl-row">
              <Bar v-for="i in [0, 1, 2, 3]" :key="i" :w="14" :h="14" :r="3" :tone="2" />
            </span>
          </div>
          <div class="xl-group">
            <span v-for="(bwItem, i) in [52, 44, 40]" :key="i" class="xl-big">
              <Bar :w="22" :h="22" :r="4" :tone="2" />
              <Bar :w="bwItem" :h="5" :tone="2" />
            </span>
          </div>
        </template>
        <div class="xl-group xl-editing">
          <span class="xl-autosum" data-target="autosum">
            <span class="xl-sigma">Σ</span>
            <span>AutoSum</span>
            <svg class="xl-caret" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
              <path d="M1.5 3 4 5.5 6.5 3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
          <span class="xl-row xl-quiet">
            <Bar :w="12" :h="12" :r="3" :tone="2" />
            <Bar :w="30" :h="5" :tone="2" />
          </span>
          <span v-if="!info.compact" class="xl-row xl-quiet">
            <Bar :w="12" :h="12" :r="3" :tone="2" />
            <Bar :w="36" :h="5" :tone="2" />
          </span>
        </div>
      </div>

      <!-- Formula bar -->
      <div class="xl-fbar">
        <span class="xl-name" data-target="namebox">
          <span>{{ info.name }}</span>
          <svg class="xl-caret" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
            <path d="M1.5 3 4 5.5 6.5 3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="xl-fx-icons">
          <span class="xl-x">✕</span>
          <span class="xl-x">✓</span>
          <span class="xl-fx">fx</span>
        </span>
        <span class="xl-formula" data-target="formula">
          <Swap :id="info.formula || 'empty'" :duration="260">
            {{ info.formula || '\u00A0' }}
          </Swap>
        </span>
      </div>

      <!-- The sheet -->
      <div
        class="xl-sheet"
        data-crop
        data-cursor="crosshair"
        :style="{
          gridTemplateColumns: `${info.g.rowHead}px ${info.widths.map((w) => `${w}px`).join(' ')}`,
          gridAutoRows: `${info.g.row}px`,
          gridTemplateRows: `${info.g.head}px`,
        }"
      >
        <div class="xl-corner" />
        <div
          v-for="l in info.letters"
          :key="l"
          class="xl-colhead"
          :data-sel="l === 'B' || undefined"
        >
          {{ l }}
        </div>
        <template v-for="r in info.g.rows" :key="r">
          <div class="xl-rowhead" :data-sel="info.inSel(r) || undefined">
            {{ r }}
          </div>
          <div class="xl-cell" :data-row="r === 1 || undefined">
            <span v-if="r === 1" class="xl-bold">Region</span>
            <template v-else-if="r >= 2 && r <= 7">{{ ROWS[r - 2][0] }}</template>
            <span v-else-if="r === 8" class="xl-bold">Total</span>
          </div>
          <div
            class="xl-cell xl-num"
            :data-target="`b${r}`"
            :data-row="r === 1 || undefined"
            :data-sel="(info.inSel(r) && s.from !== r) || undefined"
          >
            <span v-if="r === 1" class="xl-bold">Q3 Sales</span>
            <template v-else-if="r >= 2 && r <= 7">{{ fmt(ROWS[r - 2][1]) }}</template>
            <span v-else-if="r === 8" class="xl-total" :data-show="s.total || undefined">
              {{ fmt(SUM) }}
            </span>
          </div>
          <div v-for="c in info.letters.length - 2" :key="c" class="xl-cell" />
        </template>

        <!-- The selection: one green frame with the fill handle, gliding as Excel's cell cursor does -->
        <div
          class="xl-selection"
          :style="{
            left: `${info.g.rowHead + info.g.a - 1}px`,
            width: `${info.g.b + 1}px`,
            top: `${info.g.head + (info.top - 1) * info.g.row - 1}px`,
            height: `${(info.bottom - info.top + 1) * info.g.row + 1}px`,
          }"
        >
          <span class="xl-handle" />
        </div>

        <div
          class="xl-chart"
          data-cursor="pointer"
          :style="{
            left: `${info.g.chart.left}px`,
            top: `${info.g.chart.top}px`,
            width: `${info.g.chart.width}px`,
            height: `${info.g.chart.height}px`,
          }"
        >
          <div class="xl-chart-head">
            <span class="xl-chart-title">Q3 Sales by Region</span>
            <span class="xl-chart-total" :data-show="s.total || undefined">
              Total <span class="xl-chart-value">
                <!-- Reserve the final formatted width so the label stays still as digits arrive. -->
                <span class="xl-chart-value-size" aria-hidden="true">{{ fmt(SUM) }}</span>
                <Count :value="s.sum" :duration="900" />
              </span>
            </span>
          </div>
          <div class="xl-plot" :style="{ height: `${info.h}px` }">
            <div class="xl-axis">
              <span
                v-for="t in ticks"
                :key="t"
                :style="{ bottom: `${(t / MAX) * (info.h - 2) + 1}px` }"
              >
                {{ t === 0 ? '0' : `${t / 1000}k` }}
              </span>
            </div>
            <div class="xl-bars" :style="{ width: `${info.w}px`, height: `${info.h}px` }">
              <span
                v-for="t in ticks"
                :key="t"
                class="xl-gridline"
                :style="{ bottom: `${(t / MAX) * (info.h - 2) + 1}px` }"
              />
              <Chart
                kind="bars"
                :data="ROWS.map(([, v]) => v)"
                :max="MAX"
                :width="info.w"
                :height="info.h"
                show
                class="xl-chart-svg"
              />
              <span
                v-for="([, v], i) in ROWS"
                :key="i"
                class="xl-label"
                :data-show="s.labels || undefined"
                :style="{
                  left: `${i * (info.bw + info.gap) + info.bw / 2}px`,
                  bottom: `${(v / MAX) * (info.h - 2) + 4}px`,
                  transitionDelay: s.labels ? `${i * 60}ms` : `${(info.n - 1 - i) * 40}ms`,
                }"
              >
                {{ SHARE[i] }}%
              </span>
            </div>
          </div>
          <div class="xl-cats" :style="{ width: `${info.w}px` }">
            <span
              v-for="([rowName], i) in ROWS"
              :key="rowName"
              :style="{ left: `${i * (info.bw + info.gap) + info.bw / 2}px` }"
            >
              {{ rowName }}
            </span>
          </div>
        </div>
      </div>
    </Window>
  </Stage>
</template>
