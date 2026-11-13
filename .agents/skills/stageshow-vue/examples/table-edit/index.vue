<script setup lang="ts">
import { Badge, Roll, Stage, Window, type Act } from '../../kit'
import './table.css'

// Editing a cell in place: an amount in an invoices table is corrected and
// the total follows. Beats: the pointer double-clicks one amount, the cell
// becomes a field with its value selected, the new amount is typed over it,
// Enter commits, the cell washes once and the total rolls to match. Plays
// once; Replay is the reset.
//
// What makes an in-place edit read as the same cell:
// - The value doesn't move when the cell becomes a field. The field's ring
//   is drawn inside the cell and the text keeps its exact position, right
//   aligned, so only the ring and the caret arrive.
// - Select-all is shown (the value highlighted) before the first character
//   replaces it, so the typing reads as an overwrite, not an append.
// - The total changes after the commit, a beat later, not with each key:
//   the cause lands, then its effect (Roll's delay).
// - One wash on the edited cell, then gone. No toast: the table is the
//   confirmation.
//
// Real strings: every row. A table is the one place dense real data reads
// right; it is short (five rows) so none of it is noise.

type S = { edit: boolean; sel: boolean; val: string; amount: number; wash: boolean }

const ROWS = [
  { who: 'Halvorsen & Co', amount: 2400, status: 'Paid', due: 'Oct 2' },
  { who: 'Lumen Studio', amount: 1200, status: 'Open', due: 'Oct 30' },
  { who: 'Tidepool', amount: 860, status: 'Open', due: 'Nov 4' },
  { who: 'Northwind Air', amount: 3150, status: 'Overdue', due: 'Oct 12' },
  { who: 'Kite Labs', amount: 540, status: 'Paid', due: 'Oct 9' },
]
const EDIT = 1
const money = (n: number) => `$${n.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
const TONES = { Paid: 'success', Open: 'neutral', Overdue: 'danger' } as const

const initial: S = { edit: false, sel: false, val: '', amount: 1200, wash: false }
const poster: S = { ...initial, amount: 1450 }

async function script(a: Act<S>) {
  await a.wait(900)
  a.mark('open')
  await a.move({ at: 'cell', x: 0.7, y: 0.5 })
  await a.wait(200)
  await a.click({ at: 'cell', x: 0.7, y: 0.5 }, { double: true })
  a.put({ edit: true, sel: true, val: '1,200.00' })
  // Off the digits while typing, as a hand does once it goes to the keys
  await a.move({ at: 'cell', x: -0.5, y: 1.5 }, { duration: 450 })
  await a.wait(200)
  a.mark('type')
  a.put({ sel: false, val: '' })
  await a.type('val', '1,450.00', { interval: 70 })
  await a.wait(400)
  // Enter commits. No keycap: it would sit over the total, the payoff
  a.mark('commit')
  a.put({ edit: false, amount: 1450, wash: true })
  await a.wait(900)
  a.put({ wash: false })
  await a.wait(1800)
}

function rowTotal(s: S) {
  return ROWS.reduce((n, r, i) => n + (i === EDIT ? s.amount : r.amount), 0)
}
</script>

<template>
  <Stage
    :width="660"
    :height="400"
    :compact="{ below: 660, width: 358, height: 400 }"
    :initial="initial"
    :poster="poster"
    :script="script"
    play="once"
    :cursor="{ at: { x: 600, y: 350 } }"
    class="te"
    v-slot="{ state: s }"
  >
    <Window url="app.ledger.io/invoices" class="te-win">
      <div class="te-body">
        <div class="te-row te-row--head">
          <span>Customer</span>
          <span class="te-num">Amount</span>
          <span>Status</span>
          <span class="te-due">Due</span>
        </div>
        <div v-for="(r, i) in ROWS" :key="r.who" class="te-row">
          <span class="te-who">{{ r.who }}</span>
          <span
            v-if="i === EDIT"
            class="te-num te-cell"
            data-target="cell"
            :data-edit="s.edit || undefined"
            :data-wash="s.wash || undefined"
          >
            <span class="te-ring" />
            <span class="te-text">
              <template v-if="s.edit">
                <span class="te-dollar">$</span>
                <span class="te-sel" :data-on="s.sel || undefined">{{ s.val }}</span>
                <span :key="s.val" class="te-caret" :data-hide="s.sel || undefined" />
              </template>
              <template v-else>{{ money(s.amount) }}</template>
            </span>
          </span>
          <span v-else class="te-num">{{ money(r.amount) }}</span>
          <span>
            <Badge :tone="TONES[r.status as keyof typeof TONES]">{{ r.status }}</Badge>
          </span>
          <span class="te-due">{{ r.due }}</span>
        </div>
        <div class="te-row te-row--foot">
          <span>Total</span>
          <span class="te-num">
            <Roll :delay="250">{{ money(rowTotal(s)) }}</Roll>
          </span>
        </div>
      </div>
    </Window>
  </Stage>
</template>
