<script setup lang="ts">
import { Stage, Bar, Check, Count, Roll, Connector, Icon, Swap, type Act } from '../../kit'
import './pace.css'

// A cursorless payout story played once as it scrolls into view.
// Things reveal, then move to make room for what comes next; groups stagger;
// a line ties the new card to the row it came from; the payoff is annotated.
// This scene uses long arrivals and overlapping beats. Other stories can
// need different timing; see references/choreography.md.

type S = { step: number; sent: boolean }
const START: S = { step: 0, sent: false }

const ROWS = [
  { amount: '$12,400.00', w: 54 },
  { amount: '$8,915.20', w: 46 },
  { amount: '$21,060.75', w: 60 },
  { amount: '$5,330.00', w: 40 },
]

const money = (n: number) => `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const script = async (a: Act<S>) => {
  await a.wait(300)
  a.mark('reveal')
  a.put({ step: 1 }) // the balance rises in, centered, and counts up
  await a.wait(700)
  a.put({ step: 2 }) // payout rows stagger in under it
  await a.wait(1500)
  a.mark('move')
  a.put({ step: 3 }) // it slides aside as the payout card arrives
  await a.wait(1300)
  a.put({ step: 4 }) // the line draws from the row to the card
  await a.wait(1100)
  a.mark('send')
  a.put({ step: 5 }) // sending
  await a.wait(1300)
  a.put({ sent: true })
  await a.wait(500)
  a.put({ step: 6 }) // the annotation lands
}
</script>

<template>
  <Stage
    :width="640"
    :height="400"
    :compact="{ below: 600, width: 358, height: 610 }"
    :initial="START"
    play="once"
    :poster="{ step: 6, sent: true }"
    :script="script"
    class="sp"
    v-slot="{ state: s, rect, layout }"
  >
    <div class="sp-wash" />
    <section class="sp-balance" :data-in="s.step >= 1 || undefined" :data-aside="s.step >= 3 || undefined">
      <span class="sp-muted">Available balance</span>
      <Count class="sp-total" :value="s.step >= 1 ? 84210.5 : 0" :duration="1400" :format="money" />
      <Bar :w="120" :h="5" :tone="2" />
      <div class="sp-head">
        <span class="sp-strong">Payouts</span>
        <Bar :w="40" :h="5" :tone="2" />
      </div>
      <div
        v-for="(r, i) in ROWS"
        :key="i"
        class="sp-row"
        :data-target="`row-${i}`"
        :data-in="s.step >= 2 || undefined"
        :style="{ transitionDelay: s.step >= 2 ? `${i * 90}ms` : '0ms' }"
      >
        <span class="sp-bank" />
        <Bar :w="r.w" :h="5" :tone="3" />
        <span class="sp-amount">{{ r.amount }}</span>
        <!-- The payout's own row settles when it sends, closing the loop with the line -->
        <span class="sp-paid" :data-pending="(i === 0 && !s.sent) || undefined">
          <Roll v-if="i === 0" variant="fade">{{ s.sent ? 'Paid' : 'Pending' }}</Roll>
          <template v-else>Paid</template>
        </span>
      </div>
    </section>

    <!-- A full column beside the balance, top-aligned: no dead corners.
         Its contents build in a stagger once it has landed. -->
    <section class="sp-instant" data-target="instant" :data-in="s.step >= 3 || undefined">
      <div class="sp-instant__head" :style="{ '--i': 0 }">
        <span class="sp-instant__mark">
          <Icon name="bolt" :size="14" filled />
        </span>
        <span class="sp-strong">Instant payout</span>
      </div>
      <div class="sp-instant__amount" :style="{ '--i': 1 }">$12,400.00</div>
      <div class="sp-fields" :style="{ '--i': 2 }">
        <div class="sp-field">
          <span class="sp-muted">To</span>
          <span class="sp-dest">
            <span class="sp-bank sp-bank--sm" />
            Chase ···· 4821
          </span>
        </div>
        <div class="sp-field">
          <span class="sp-muted">Fee</span>
          <span>$124.00</span>
        </div>
      </div>
      <!-- Each state is its own centered group, crossfading in place: nothing
           ever re-centers or slides sideways between states -->
      <div class="sp-button" :style="{ '--i': 3 }" :data-sent="s.sent || undefined">
        <span class="sp-state" :data-on="s.step < 5 || undefined">
          Pay out now
        </span>
        <!-- Sending and Sent are one group: one Check turns pending, then
             fills and draws its tick. The label is a Swap, so its box
             eases to the new word and the group re-centers with it: a
             box held at "Sending" would leave "Sent" off center -->
        <span class="sp-state" :data-on="s.step >= 5 || undefined">
          <Check :on="s.sent" :pending="!s.sent" :size="14" />
          <Swap :id="s.sent ? 'sent' : 'sending'">{{ s.sent ? 'Sent' : 'Sending' }}</Swap>
        </span>
      </div>
    </section>

    <Connector
      v-if="rect('row-0').width > 0 && rect('instant').width > 0"
      :show="s.step >= 4"
      :from="{
        x: layout === 'compact' ? rect('row-0').x - 6 : rect('row-0').x + rect('row-0').width + 6,
        y: rect('row-0').y + rect('row-0').height / 2,
      }"
      :to="{
        x: rect('instant').x,
        y: layout === 'compact' ? rect('instant').y + 24 : rect('row-0').y + rect('row-0').height / 2,
      }"
      :route="layout === 'compact' ? 'v' : 'straight'"
    />

    <div
      class="sp-note"
      :data-in="s.step >= 6 || undefined"
      :style="{ left: `${rect('instant').x}px`, top: `${rect('instant').y + rect('instant').height + 16}px` }"
    >
      Arrives in about 30 minutes
    </div>
  </Stage>
</template>
